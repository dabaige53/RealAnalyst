# 错误处理

> RealAnalyst 的脚本主要是 CLI 工具。错误必须对 agent/用户可见；当调用方需要 JSON 时，错误也必须可机器读取；错误信息要能指向具体破坏的契约。

---

## 总体风格

写文件或查询数据前先做显式校验。脚本通常返回三类形态：

- 面向 agent 的命令输出 JSON success/failure payload。
- CLI 使用错误或缺依赖时，使用 `SystemExit` 加短消息。
- 底层 helper 抛 Python exception，由需要结构化响应的 CLI wrapper 捕获并转成 JSON。

不要静默吞错。不要把具体 validation failure 替换成泛泛的 “failed”。

---

## 自定义错误类型

`skills/metadata/lib/metadata_io.py` 定义了主要 metadata 异常：

```python
class MetadataError(ValueError):
    """Raised when metadata YAML cannot be loaded or normalized."""
```

这些问题使用 `MetadataError`：

- dataset id 非法。
- dataset id 匹配多个文件。
- dataset 文件不存在。
- YAML 无法解析。
- YAML payload 不是 mapping。

`MetadataError` 只用于 metadata I/O 和 normalization。命令参数语义、业务校验失败等其它场景，使用 `ValueError` 或结构化 JSON error。

---

## 校验错误（validation）

Metadata validation 会收集所有已知错误后一起返回，参考 `skills/metadata/scripts/validate_metadata.py`：

```python
errors: list[str] = []
for key in REQUIRED_DATASET_KEYS:
    require(data, key, errors, path.name)
```

这样做是为了支持 metadata 迭代维护：用户一次看到所有放错层、缺定义、重复定义的问题，而不是每次 rerun 只暴露一个。

重要 validation contract：

- Dataset YAML 拒绝 `sample_profile`、`sample_values`、`top_values`、`enum_values`、`source_mapping`、`duckdb_type`、`nullable`。
- Dataset field/metric 的业务定义要用 `business_definition.ref` 引用 dictionary 或 mapping，不展开 `source_evidence`。
- Pending 定义使用 `text: 业务定义待确认` 和 `needs_review: true`。
- Pending 定义不能注册为 formal metrics。
- Dataset YAML 超过 1000 行 warning，超过 1500 行失败。
- `description` 和 `business_definition.text` 不能完全重复。

新增 validator 时，错误要写清具体文件、section、key path，例如：

```text
demo.retail.orders.yaml.fields[3].business_definition.ref is required when source_type=dictionary
```

---

## 结构化错误响应（JSON）

面向 agent 的 wrapper 至少输出：

```json
{
  "success": false,
  "error": "human-readable message",
  "error_code": "STABLE_CODE"
}
```

`skills/data-profile/scripts/run.py` 是现有模式：

```python
def _error(message: str, *, error_code: str, extra: dict[str, Any] | None = None) -> int:
    payload = {
        "success": False,
        "error": message,
        "error_code": error_code,
    }
    if extra:
        payload.update(extra)
    return _emit(payload, exit_code=1)
```

当另一个 skill、agent 或测试会按失败原因分支时，使用稳定 `error_code`。已有示例：

- `OUTPUT_DIR_REQUIRED`
- `EXPORT_SUMMARY_NOT_FOUND`
- `MULTIPLE_CSV_CANDIDATES`
- `EXPORT_SUMMARY_INVALID`
- `DATA_CSV_NOT_FOUND`

---

## 命令退出规则（CLI exit）

- 成功返回 `0`。
- validation、data、runtime failure 返回 `1`。
- CLI misuse 返回 `2`，通常由 `argparse` 或脚本显式报告缺 required mode。

真实示例：

- `skills/metadata/scripts/sync_registry.py` 只有当所有请求 dataset 状态为 `preview` 或 `synced` 时返回 `0`。
- `skills/metadata-report/scripts/generate_report.py` 在既没有 `--connector` 也没有 connector-prefixed `--dataset-id` 时返回 `2`。
- `skills/metadata-report/scripts/generate_report.py` 遇到 YAML report generation validation errors 时返回 `1`。

---

## 依赖错误

可选依赖只在请求动作需要它时才失败，并给出安装提示。现有模式：

```python
except ModuleNotFoundError as exc:
    raise SystemExit("duckdb is required. Install dependencies with: pip install -r requirements.txt") from exc
```

这个模式出现在 `examples/build_demo_duckdb.py` 和 DuckDB export/report flow 中。依赖错误要可执行，不要隐藏“操作没有运行”的事实。

---

## 路径安全错误

读取 JSON manifest 或用户传入 summary 中的路径时，必须防 path escape。

`skills/data-profile/scripts/run.py` 会检查 Tableau summary 路径在 job output directory 内，DuckDB summary 路径在 workspace 内：

```python
candidate.relative_to(output_dir.resolve())
candidate.relative_to(_workspace_dir().resolve())
```

新增读取 manifest path 的脚本时沿用这个模式。

---

## 导出错误（export）

受控 exporter 应在读取数据前校验：

- 缺 `source_id`。
- source 非 active。
- source backend 不匹配。
- 临时/废弃对象名。
- 缺 runtime spec。
- selected/filter/group/order/aggregate 字段未注册。
- filter/date/order/aggregate 语法非法。

`skills/data-export/scripts/duckdb/export_duckdb_source.py` 使用直接中文错误，例如 `未找到 source_id`、`存在未注册字段`、`非法 filter 语法`。保持具体，不要改成泛泛的英文错误。

---

## 报告生成错误

Metadata report generation 缺输入时不能编占位内容。

遵循 `skills/metadata-report/scripts/generate_report.py`：

- YAML 无效时打印 `[Error] metadata validate failed:` 并列出 validation errors。
- scoped report 找不到目标时打印 `[WARN] No DuckDB entries matched` 或 `[WARN] No Tableau entries matched`。
- CLI mode 不完整时退出。

Report scripts 对没有可验证来源的 section 应删除或省略，不要填泛化文本。

---

## 常见错误

- `except Exception` 后继续产出 partial output，却没有设置 `success: false`。
- 调用方期待 JSON 时输出 plain text。
- 跳过必要 validation、registry sync 或 report section 后仍返回 success。
- `validate_metadata.py` 已经视为 error 的 metadata 分层问题，被其它脚本降级成 warning。
- 在 data profiling 或 sample collection 外围写 `except Exception: pass`，且没有记录样本不可用原因。

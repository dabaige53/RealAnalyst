# RA:data-analytics-semantic-export

把 RealAnalyst metadata 导出成 Data Analytics 可读取的 semantic-layer skill package。它只生成使用副本，不修改 Data Analytics 插件、不自动写 Data Analytics `user-context`，也不改 RealAnalyst 正式 metadata。

---

## 什么时候用？

- 需要把一个或多个 RealAnalyst dataset 交给 Data Analytics 做后续分析、report 或 dashboard。
- 需要生成可复用的 metrics、fields、source inventory、filters、caveats、freshness 和 provenance 指导。
- 需要把项目本地 metadata 投影到全局 `$CODEX_HOME/skills/<area-slug>-semantic-layer/`。

**不要用于**：

- 注册或修正 RealAnalyst metadata；使用 `RA:metadata` / `RA:metadata-refine`。
- 取数、画像、写报告或报告验证；使用 `RA:analysis-run` 及流程内 skill。
- 自动写 Data Analytics `user-context`；注册指针必须后续获得用户明确批准。

---

## 主要输入

| 输入 | 来源 |
| --- | --- |
| `metadata/datasets/*.yaml` | dataset 身份、字段、指标、粒度和适用边界 |
| `metadata/dictionaries/*.yaml` | 标准指标、字段和术语定义 |
| `metadata/mappings/*.yaml` | 源字段到标准语义的映射 |
| `metadata/audit/*` | 关系和维护追溯路径 |
| `runtime/registry.db` | 运行态 source 注册状态，不作为业务定义真源 |

## 主要输出

| 输出 | 说明 |
| --- | --- |
| `SKILL.md` | Data Analytics 可加载的小型 semantic-layer skill 入口 |
| `references/semantic-layer.md` | metrics、fields、filters、tables、query patterns、caveats 和 open questions |
| `references/source-inventory.md` | source priority、覆盖程度、权限状态、缺口和更新边界 |

---

## 快速开始

```bash
python3 skills/metadata/scripts/metadata.py validate

python3 skills/data-analytics-semantic-export/scripts/export_semantic_layer.py \
  --area <area> \
  --dataset-id <dataset_id> \
  --output-dir <temp_or_target_package_dir>
```

不传 `--output-dir` 时，默认写入：

```text
$CODEX_HOME/skills/<area-slug>-semantic-layer/
```

如需避免同名冲突，显式传 `--skill-name <custom-name>`；脚本不会自动追加 RealAnalyst 或项目名前缀。

---

## 常见卡点

| 卡点 | 处理 |
| --- | --- |
| stdout 解析失败 | 脚本成功和预期失败都应输出 JSON；先看 `error_code` |
| dataset validation 失败 | 回到 `RA:metadata` 修 YAML 分层或定义引用 |
| registry 未注册 | package 仍生成，但 source inventory 会标记 `runtime registry not registered` |
| 需要 Data Analytics 长期发现 | 等用户批准后，再把 JSON summary 里的 `suggested_user_context_entry` 写入 Data Analytics `user-context` |
| 担心敏感信息 | 生成内容会脱敏 locator，并排除 secrets、DSN、token、row-level sample 和长私有摘录 |

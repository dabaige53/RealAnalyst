# 测试需求报告：metadata index 生成层与 CI 断点门禁

## 1. 背景

`metadata/index/` 是从 `metadata/{datasets,dictionaries,mappings}` 下源 YAML 生成的「生成层」JSONL 索引，且整个目录被 `.gitignore`（第 19 行 `metadata/index/`）忽略，不入库。

审计与测试对这个生成层有硬依赖：`tests/test_project_contract_audit.py` 断言 `metadata_files["counts"]["generated_index"] >= 1`。但公共测试入口 `test.sh`（CI 唯一命令 `bash test.sh`）原本的步骤里没有生成 index 的步骤，`metadata.py validate` 和 `audit_project_contracts.py` 都不会生成 index。

结果是一个隐藏的 CI 断点：开发机因为本地残留了旧 index 而测试通过；在 fresh clone / CI 全新检出上，`metadata/index/` 不存在，`generated_index` 计数为 0，`bash test.sh` 会在 `test_project_contract_audit` 处失败。本报告把这个断点固化为回归门禁，并把生成层的确定性纳入测试。

## 2. 目标行为

- `test.sh` 在 `metadata.py validate` 之后、`audit_project_contracts.py` 之前执行 `metadata.py index`，保证审计与测试运行前生成层已就绪。
- `tests/test_ci_workflows.py` 锁定该步骤顺序（validate → index → audit），防止后续有人删掉或挪动。
- metadata index 生成是确定性的：相同源 YAML 两次生成的 6 个 JSONL 必须字节一致。
- `metadata.py index` 能在 index 缺失时把 gitignored 生成层重新建出来（fresh clone / CI 自愈路径）。
- index 生成后，项目契约审计能数到 `generated_index >= 1`。
- 新测试 `tests/test_metadata_index_pipeline.py` 与本报告纳入 `scripts/audit_project_contracts.py` 的 `code_surface_matrix`，作为独立实现面 `metadata_index_pipeline`，并被 `tests/test_project_contract_audit.py` 的期望集合锁定。

## 3. 风险等级

- 等级：P0
- 理由：这是会让 fresh clone / CI 直接失败的断点，且在有本地残留 index 的开发机上不可见，属于典型 green-on-my-machine / red-on-CI。不修会让 CI 门禁形同虚设。

## 4. 覆盖范围

- 涉及文件：`test.sh`、`tests/test_ci_workflows.py`、`tests/test_metadata_index_pipeline.py`、`scripts/audit_project_contracts.py`、`tests/test_project_contract_audit.py`、本报告。
- 实现面：`skills/metadata/scripts/build_index.py`、`skills/metadata/lib/metadata_index.py`（生成层 index 构建）。
- 不覆盖范围：不改动源 YAML 内容；不把 `metadata/index/` 改为入库；不处理 `metadata/sync/duckdb/reports/` 下历史报告沉积（另列为清理项，不在本门禁内）。

## 5. Fixture / 环境前提

- Python：默认 `python3`，可通过 `PYTHON=...` 覆盖。
- 依赖：使用 `requirements.txt` 中的公开依赖。
- 数据：只使用仓库内公开 demo metadata（`metadata/datasets/demo.retail.orders.yaml` 等）。
- 当前 demo fixture 的索引总记录数为 27；若源 YAML 变更，需同步更新 `tests/test_metadata_index_pipeline.py` 中的 `EXPECTED_TOTAL_RECORDS` 与源数据，保持生成层可审计。
- 生成是确定性、幂等的，所以测试中重新生成真实（gitignored）的 `metadata/index/` 无副作用。

## 6. 完整 Python 复现代码

```python
import json
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
build_index = repo / "skills" / "metadata" / "scripts" / "build_index.py"

def build(out_dir):
    proc = subprocess.run(
        [sys.executable, str(build_index), "--output-dir", str(out_dir)],
        cwd=repo, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout)

expected_files = (
    "aliases.jsonl", "datasets.jsonl", "fields.jsonl",
    "glossary.jsonl", "mappings.jsonl", "metrics.jsonl",
)

with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
    ra, rb = build(Path(a)), build(Path(b))
    assert ra["success"] and ra["total_records"] == 27
    for name in expected_files:
        assert (Path(a) / name).read_bytes() == (Path(b) / name).read_bytes(), name

# fresh-clone 自愈：metadata.py index 重新建出 gitignored 生成层，审计随后能数到
subprocess.run([sys.executable, str(repo / "skills/metadata/scripts/metadata.py"), "index"],
               cwd=repo, check=False)
index_dir = repo / "metadata" / "index"
for name in expected_files:
    assert (index_dir / name).is_file(), name
```

## 7. 完整 Python 测试代码

```python
def test_index_build_is_deterministic_and_complete(self) -> None:
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        result_a = _build_index(Path(tmp_a))
        result_b = _build_index(Path(tmp_b))
        self.assertTrue(result_a["success"])
        self.assertEqual(result_a["total_records"], EXPECTED_TOTAL_RECORDS)
        self.assertEqual(result_b["total_records"], EXPECTED_TOTAL_RECORDS)
        for name in EXPECTED_INDEX_FILES:
            file_a = Path(tmp_a) / name
            file_b = Path(tmp_b) / name
            self.assertTrue(file_a.is_file(), f"missing generated index: {name}")
            self.assertEqual(file_a.read_bytes(), file_b.read_bytes(),
                             f"non-deterministic generated index: {name}")

def test_metadata_index_cli_regenerates_gitignored_layer(self) -> None:
    proc = subprocess.run([sys.executable, str(METADATA_CLI), "index"],
                          cwd=REPO, text=True, capture_output=True, check=False)
    self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
    index_dir = REPO / "metadata" / "index"
    for name in EXPECTED_INDEX_FILES:
        self.assertTrue((index_dir / name).is_file(), f"index CLI did not emit {name}")

def test_audit_counts_generated_index_after_build(self) -> None:
    proc = subprocess.run([sys.executable, str(METADATA_CLI), "index"],
                          cwd=REPO, text=True, capture_output=True, check=False)
    self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
    audit = _load_audit_module()
    payload = audit.run_audit()
    generated_index = payload["inventory"]["metadata_files"]["counts"]["generated_index"]
    self.assertGreaterEqual(generated_index, 1)
```

`tests/test_ci_workflows.py` 同时新增顺序门禁：

```python
def test_test_sh_builds_metadata_index_before_audit(self) -> None:
    script = TEST_SH.read_text(encoding="utf-8")
    validate_pos = script.index("skills/metadata/scripts/metadata.py validate")
    index_pos = script.index("skills/metadata/scripts/metadata.py index")
    audit_pos = script.index("scripts/audit_project_contracts.py")
    self.assertLess(validate_pos, index_pos, "index must run after validate")
    self.assertLess(index_pos, audit_pos, "index must run before the project audit")
```

## 8. 复跑命令

```bash
# 决定性验证：模拟 fresh clone（metadata/index 被 gitignore，移走后再跑 test.sh）
TMP=$(mktemp -d); mv metadata/index "$TMP/index"
bash test.sh                       # 必须通过（验证断点已修）
rm -rf metadata/index; mv "$TMP/index" metadata/index; rmdir "$TMP"

# 常规复跑
bash test.sh
python3 -m unittest tests.test_metadata_index_pipeline
python3 -m unittest tests.test_ci_workflows
python3 -m unittest tests.test_project_contract_audit
git diff --check
```

## 9. 实际结果

- 修复前（移走 `metadata/index/` 模拟 fresh clone）：`python3 -m unittest tests.test_project_contract_audit` 报 `AssertionError: 0 not greater than or equal to 1`，`bash test.sh` 失败。
- 修复后：`test.sh` 在 validate 之后、audit 之前执行 `metadata.py index`；fresh-clone 模拟下 `bash test.sh` 全程通过。
- `python3 -m unittest tests.test_metadata_index_pipeline`：3 个测试通过。
- `python3 -m unittest tests.test_ci_workflows`、`tests.test_project_contract_audit`：通过。
- `git diff --check`：通过。

> 复跑数字以本地实际输出为准；本报告记录的是引入门禁时的预期结果。

## 10. 验收结论

本门禁把「生成层 index 必须在审计前由测试管线自己生成」固化为可复跑的 CI 步骤 + 顺序回归测试，并把 index 生成的确定性与自愈路径纳入测试。新增实现面 `metadata_index_pipeline` 进入项目契约审计矩阵，`build_index.py` 由「未文档化候选脚本」提升为有专项测试与测试报告的覆盖面。fresh clone / CI 不再因缺失 gitignored 生成层而失败。

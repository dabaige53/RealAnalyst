# 测试需求报告：code surface 测试与报告覆盖矩阵

## 1. 背景

项目目标要求所有 Skills 和代码实现点都能被校验，并且每份代码和实现点都有相关测试文档和测试脚本。已有 `scripts/audit_project_contracts.py` 能输出 Skill、代码和 metadata inventory，但还缺少“关键实现面 -> 测试文件 -> 测试报告”的机器可读矩阵。

本次调整把关键实现面固化为 `code_surface_matrix`，并把它纳入项目契约审计。同时新增 `code_file_coverage`，把仓库内每个 Python 文件归入明确的测试/文档覆盖策略。后续新增核心实现面时，必须同步补实现文件、测试文件和 `tests/reports/*.md` 复跑报告；后续新增普通 Python 文件时，也必须能被覆盖策略分类，不能变成无人负责的脚本。

## 2. 目标行为

- `scripts/audit_project_contracts.py` 输出 `inventory.code_surface_matrix`。
- 每个 code surface 至少列出实现文件、测试文件和测试需求报告。
- 审计失败条件包括：实现文件不存在、测试文件不存在、测试报告不存在或报告未提到 surface id 与测试文件名。
- `scripts/audit_project_contracts.py` 输出 `inventory.code_files.code_file_coverage`。
- 每个 Python 文件必须有分类、owner、测试文件和测试报告；未分类文件会让项目契约审计失败。
- `tests/test_project_contract_audit.py` 固定当前矩阵范围，防止新增/删除实现面时无感漂移。

## 3. 风险等级

- 等级：P1
- 理由：没有覆盖矩阵时，仓库可能“有测试”和“有文档”，但无法证明具体实现点被哪个测试和哪份复跑报告覆盖。

## 4. 覆盖范围

当前矩阵覆盖 11 个关键实现面：

| Surface | 实现文件 | 测试文件 |
| --- | --- | --- |
| `one_click_test_entry` | `test.sh`, `.github/workflows/ci.yml` | `tests/test_ci_workflows.py` |
| `project_contract_audit` | `scripts/audit_project_contracts.py` | `tests/test_project_contract_audit.py` |
| `job_manifest_runtime` | `runtime/job_manifest.py`, `schemas/job_manifest.schema.json` | `tests/test_job_manifest.py` |
| `analysis_run_job_lifecycle` | `skills/analysis-run/scripts/init_or_resume_job.py`, `skills/analysis-run/scripts/render_user_reply.py` | `tests/test_analysis_run_manifest_integration.py` |
| `analysis_plan_contract` | `skills/analysis-plan/scripts/validate_plan.py`, `skills/analysis-reference/scripts/query_config.py`, `skills/reference-lookup/scripts/query_config.py`, `schemas/analysis_plan_decision.schema.json` | `tests/test_analysis_plan_contract.py`, `tests/test_analysis_reference_frameworks.py` |
| `artifact_registration` | `scripts/update_artifact_index.py`, `schemas/manifest.schema.json` | `tests/test_export_profile_manifest_registration.py` |
| `report_manifest_delivery` | `skills/report/scripts/append_report_update.py` | `tests/test_report_manifest_deliverables.py` |
| `report_verify_user_surface` | `skills/report-verify/scripts/verify.py`, `schemas/verification.schema.json` | `tests/test_report_verify_user_surface.py` |
| `legacy_migration_archive` | `scripts/legacy_job_manifest_migration.py`, `scripts/finalize_job_archive.py` | `tests/test_legacy_job_manifest_migration.py`, `tests/test_finalize_job_archive.py` |
| `metadata_layering_and_references` | `skills/metadata/scripts/validate_metadata.py`, demo metadata YAML | `tests/test_metadata_product_fixes.py`, `tests/test_project_contract_audit.py` |
| `metadata_index_pipeline` | `skills/metadata/scripts/build_index.py`, `skills/metadata/lib/metadata_index.py` | `tests/test_metadata_index_pipeline.py` |

全 Python 文件覆盖策略包含以下分类：

| Category | 含义 | 测试策略 |
| --- | --- | --- |
| `code_surface` | 已进入关键实现面矩阵的核心代码 | 对应专项测试 + 本报告 |
| `automated_test` | `tests/test_*.py` 自动测试文件 | 文件自身由 `unittest discover` 收集 |
| `documented_skill_script` | 已被 Skill 文档或 README 直接提到的脚本 | 项目契约审计验证文档与脚本关系 |
| `internal_or_unreferenced_skill_script` | 未被 Skill 文档/README 提到的脚本（应为空） | 已收敛为 0；`test_no_unaccounted_skill_scripts` 断言该清单恒为空 |
| `metadata_adapter_script` | metadata adapter 下的 ClickHouse、DuckDB、MySQL、Tableau 等数据源脚本 | 项目契约审计 + metadata 产品修复测试覆盖分层边界 |
| `platform_integration_support` | `.codex` / `.claude` 等平台集成脚本 | 项目契约审计保证归类和报告追踪 |
| `trellis_runtime_support` | `.trellis` 运行时支撑脚本 | 项目契约审计保证归类和报告追踪 |
| `runtime_support` | `runtime/` 运行时支撑模块 | 关键 runtime 走专项测试，其余进入项目审计 |
| `project_script` | `scripts/` 下的项目级脚本 | 关键脚本走专项测试，其余进入项目审计 |
| `skill_library_or_bootstrap` | Skill 内部库和 bootstrap | 项目契约审计保证归类和报告追踪 |
| `manual_smoke_script` | `tests/` 外的手动 smoke 脚本 | 项目契约审计保证不会被 pytest 误收集 |
| `shared_library_support` / `example_support` | 共享库或示例代码 | 项目契约审计保证归类和报告追踪 |

不覆盖范围：本矩阵不声明每个内部 helper 都已有专项业务测试；但每个 skill 脚本都必须在其 SKILL.md 或 README 问责（入口或声明为内部模块），`inventory.code_files.potentially_internal_or_unreferenced_skill_scripts` 现已收敛为 0，并由 `test_no_unaccounted_skill_scripts` 守护。

## 5. Fixture / 环境前提

- 使用仓库内公开文件和 demo metadata。
- 不连接真实 Tableau、DuckDB、MySQL、ClickHouse 或生产凭证。
- 审计脚本只读，不写工作区。

## 6. 完整 Python 复现代码

```python
import importlib.util
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
script = repo / "scripts" / "audit_project_contracts.py"
spec = importlib.util.spec_from_file_location("project_contract_audit", script)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

payload = module.run_audit()
assert payload["success"] is True
matrix = payload["inventory"]["code_surface_matrix"]
assert len(matrix) >= 10

for surface in matrix:
    for path in surface["implementation_paths"]:
        assert (repo / path).exists(), (surface["id"], path)
    for path in surface["test_paths"]:
        assert (repo / path).exists(), (surface["id"], path)
    report_text = "\n".join((repo / path).read_text(encoding="utf-8") for path in surface["report_paths"])
    assert surface["id"] in report_text
    for test_path in surface["test_paths"]:
        assert Path(test_path).name in report_text

code_files = payload["inventory"]["code_files"]
coverage = code_files["code_file_coverage"]
assert len(coverage) == code_files["python_file_count"]
assert not [item for item in coverage if item["category"] == "unclassified"]
for item in coverage:
    assert item["test_paths"], item["path"]
    assert item["report_paths"], item["path"]
    for path in item["test_paths"] + item["report_paths"]:
        assert (repo / path).exists(), (item["path"], path)

categories = {item["category"] for item in coverage}
assert "code_surface" in categories
assert "metadata_adapter_script" in categories
assert "platform_integration_support" in categories
assert "trellis_runtime_support" in categories
```

## 7. 完整 Python 测试代码

```python
def test_audit_inventory_covers_code_surface_test_document_matrix(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    matrix = payload["inventory"]["code_surface_matrix"]
    surfaces = {item["id"]: item for item in matrix}

    expected_surfaces = {
        "one_click_test_entry",
        "project_contract_audit",
        "job_manifest_runtime",
        "analysis_run_job_lifecycle",
        "analysis_plan_contract",
        "artifact_registration",
        "report_manifest_delivery",
        "report_verify_user_surface",
        "legacy_migration_archive",
        "metadata_layering_and_references",
        "metadata_index_pipeline",
    }
    self.assertEqual(set(surfaces), expected_surfaces)
    for surface in matrix:
        for path in surface["implementation_paths"] + surface["test_paths"] + surface["report_paths"]:
            self.assertTrue((REPO / path).exists(), f"{surface['id']} missing {path}")

    self.assertIn("runtime/job_manifest.py", surfaces["job_manifest_runtime"]["implementation_paths"])
    self.assertIn("tests/test_job_manifest.py", surfaces["job_manifest_runtime"]["test_paths"])
    self.assertIn(
        "tests/reports/2026-06-18-code-surface-coverage.md",
        surfaces["job_manifest_runtime"]["report_paths"],
    )

def test_audit_inventory_classifies_every_python_file_with_test_strategy(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    code_files = payload["inventory"]["code_files"]
    coverage = code_files["code_file_coverage"]

    self.assertEqual(len(coverage), code_files["python_file_count"])
    self.assertFalse([item for item in coverage if item["category"] == "unclassified"])
    for item in coverage:
        self.assertTrue(item["test_paths"], item["path"])
        self.assertTrue(item["report_paths"], item["path"])
        for path in item["test_paths"] + item["report_paths"]:
            self.assertTrue((REPO / path).exists(), f"{item['path']} references missing {path}")

    categories = {item["category"] for item in coverage}
    self.assertIn("code_surface", categories)
    self.assertIn("documented_skill_script", categories)
    self.assertNotIn("internal_or_unreferenced_skill_script", categories)
    self.assertIn("metadata_adapter_script", categories)
    self.assertIn("platform_integration_support", categories)
    self.assertIn("trellis_runtime_support", categories)
```

## 8. 复跑命令

```bash
python3 scripts/audit_project_contracts.py
python3 -m unittest tests.test_project_contract_audit
bash test.sh
```

测试语言统一为 Python。`test.sh` 只是项目级一键入口，内部测试仍执行 Python 审计、Python unittest 和 Python 回归脚本；本次调整不需要 JS 测试代码。

## 9. 实际结果

- 已通过：`python3 scripts/audit_project_contracts.py`，输出 `success=true`，error/warning 均为 0，并包含 `inventory.code_surface_matrix`。
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，`Ran 14 tests ... OK`。
- 已通过：`bash test.sh`，其中 `python3 -m unittest discover -s tests` 输出 `Ran 100 tests ... OK`，`python3 scripts/run_manifest_workflow_regression.py` 输出 `42 passed, 9 subtests passed`。
- 已通过：`git diff --check`。
- 注意：`unittest discover` 阶段仍出现 sqlite connection ResourceWarning，但不影响测试结果；该项属于后续清理项，不阻塞本轮验收。

## 10. 验收结论

本报告用于把代码实现面、测试文件和复跑报告绑定成可审计矩阵。专项审计、单元测试、全量发现测试、manifest 回归和 `git diff --check` 均已通过；`bash test.sh` 作为全项目公开测试入口已完成真实验收。

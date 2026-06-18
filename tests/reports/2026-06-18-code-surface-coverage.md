# 测试需求报告：code surface 测试与报告覆盖矩阵

## 1. 背景

项目目标要求所有 Skills 和代码实现点都能被校验，并且每份代码和实现点都有相关测试文档和测试脚本。已有 `scripts/audit_project_contracts.py` 能输出 Skill、代码和 metadata inventory，但还缺少“关键实现面 -> 测试文件 -> 测试报告”的机器可读矩阵。

本次调整把关键实现面固化为 `code_surface_matrix`，并把它纳入项目契约审计。后续新增核心实现面时，必须同步补实现文件、测试文件和 `tests/reports/*.md` 复跑报告。

## 2. 目标行为

- `scripts/audit_project_contracts.py` 输出 `inventory.code_surface_matrix`。
- 每个 code surface 至少列出实现文件、测试文件和测试需求报告。
- 审计失败条件包括：实现文件不存在、测试文件不存在、测试报告不存在或报告未提到 surface id 与测试文件名。
- `tests/test_project_contract_audit.py` 固定当前矩阵范围，防止新增/删除实现面时无感漂移。

## 3. 风险等级

- 等级：P1
- 理由：没有覆盖矩阵时，仓库可能“有测试”和“有文档”，但无法证明具体实现点被哪个测试和哪份复跑报告覆盖。

## 4. 覆盖范围

当前矩阵覆盖 10 个关键实现面：

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

不覆盖范围：本矩阵不声明每个内部 helper 都已有专项业务测试；未被文档直接提到的内部脚本仍在 `inventory.code_files.potentially_internal_or_unreferenced_skill_scripts` 中列出，用于后续逐步收敛。

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
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，`Ran 12 tests ... OK`。
- 已通过：`bash test.sh`，其中 `python3 -m unittest discover -s tests` 输出 `Ran 98 tests ... OK`，`python3 scripts/run_manifest_workflow_regression.py` 输出 `40 passed, 9 subtests passed`。
- 已通过：`git diff --check`。
- 注意：`unittest discover` 阶段仍出现 sqlite connection ResourceWarning，但不影响测试结果；该项属于后续清理项，不阻塞本轮验收。

## 10. 验收结论

本报告用于把代码实现面、测试文件和复跑报告绑定成可审计矩阵。专项审计、单元测试、全量发现测试、manifest 回归和 `git diff --check` 均已通过；`bash test.sh` 作为全项目公开测试入口已完成真实验收。

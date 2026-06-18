# 测试需求报告：全项目 Skills / 代码 / metadata 交付链审计

## 1. 背景

当前目标是对 RealAnalyst 的所有 Skills、代码、Skill 交付链和 metadata 资产做系统校验，找出介绍信息与代码不一致、代码缺陷、交付物断档、未使用文件、脏内容和复跑测试缺口。这个范围不能只靠一次人工阅读，需要沉淀成可重复运行的审计脚本和测试报告。

## 2. 目标行为

- 每个 `skills/*/SKILL.md` 的介绍信息、README、脚本目录、references 目录之间有基础一致性检查。
- 每个 Skill 声明的脚本、references、交付物契约能被脚本化审计到，不只靠人工记忆；审计 inventory 要列出每个 Skill 的脚本和 reference 文件。
- 核心交付链 `getting-started -> metadata -> analysis-run -> analysis-plan -> data-export -> data-profile -> report -> report-verify` 的相邻 handoff 必须被脚本化审计；每条相邻链路都要验证 producer outputs、consumer inputs、trigger/next step 和 state update 能在对应 Skill 文档中找到。
- 审计 JSON 必须输出 Skill inventory、代码文件 inventory、metadata 文件清单和核心交付链顺序，方便后续排查 Skill 介绍、代码入口和交付物是否断档。
- 代码文件 inventory 必须覆盖 Python 文件、自动测试、runtime 文件、project scripts、Skill scripts、未被 Skill/README 直接提到但可能属于内部 helper 的脚本、手动 smoke 脚本。
- metadata inventory 必须输出 datasets、dictionaries、mappings、models、sources、sync reports、generated index 的数量，用于识别未使用文件、生成层内容和历史报告沉积。
- metadata 目录中不应出现明显分层污染、生成层手工内容、断裂 source evidence、未被入口引用的脏文件或旧报告冒充真源。
- 代码审计至少覆盖 Python 语法、测试收集、核心回归、schema JSON、CI workflow 与 `test.sh` 一致性。
- 审计输出是结构化 JSON，并能作为后续修复任务的输入。
- 审计报告必须完整列出未被 Skill/README 直接提到的内部/辅助脚本候选，不能只在 JSON inventory 中隐藏。

## 3. 风险等级

- 等级：P1
- 理由：如果 Skill 文档、代码入口、metadata 文件和交付链不一致，用户会在 analysis-run/report/export/profile 之间遇到断点；如果审计不可复跑，每次修复都会重新依赖人工排查。

## 4. 覆盖范围

- 涉及文件：`skills/**`、`metadata/**`、`schemas/**`、`scripts/**`、`runtime/**`、`tests/**`、`test.sh`、`.github/workflows/*.yml`。
- 涉及入口：`bash test.sh`、`scripts/run_manifest_workflow_regression.py`、新增项目审计脚本。
- 不覆盖范围：不连接真实 Tableau、DuckDB、MySQL、ClickHouse 或生产凭证；不读取真实私有 job 数据；不替代后续针对具体 bug 的修复测试。

## 5. Fixture / 环境前提

- Python：默认 `python3`，可通过 `PYTHON=...` 覆盖。
- 依赖：使用 `requirements.txt` 中的公开依赖。
- 数据：只使用仓库内公开 demo metadata、schema、Skill 文档和临时 fixture。
- 输出：审计脚本默认只读；如需要保存报告，应写到 `tests/reports/` 或明确的临时输出目录。

## 6. 完整 Python 复现代码

```python
import json
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
proc = subprocess.run(
    [sys.executable, "scripts/audit_project_contracts.py"],
    cwd=repo,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
assert proc.returncode == 0, proc.stdout + proc.stderr
payload = json.loads(proc.stdout)
assert payload["success"] is True
assert payload["summary"]["findings"]["error"] == 0
assert payload["summary"]["findings"]["warning"] == 0

handoff_matrix = payload["inventory"]["handoff_matrix"]
expected_chain = [
    "getting-started",
    "metadata",
    "analysis-run",
    "analysis-plan",
    "data-export",
    "data-profile",
    "report",
    "report-verify",
]
assert [(edge["from"], edge["to"]) for edge in handoff_matrix] == list(
    zip(expected_chain, expected_chain[1:])
)
assert all(edge["complete"] for edge in handoff_matrix)

code_files = payload["inventory"]["code_files"]
assert code_files["python_file_count"] >= 50
assert "runtime/job_manifest.py" in code_files["runtime_files"]
assert "scripts/audit_project_contracts.py" in code_files["project_scripts"]
assert "tests/test_project_contract_audit.py" in code_files["test_files"]
assert "skills/metadata/adapters/tableau/scripts/test_views.py" in code_files["manual_smoke_scripts_outside_tests"]
assert "skills/data-export/scripts/sql/common_sql_export.py" in code_files["potentially_internal_or_unreferenced_skill_scripts"]

metadata_files = payload["inventory"]["metadata_files"]
assert metadata_files["counts"]["sync_reports"] >= 1
assert metadata_files["counts"]["generated_index"] >= 1

for script_path in code_files["potentially_internal_or_unreferenced_skill_scripts"]:
    print(script_path)
```

## 7. 完整 Python 测试代码

```python
def test_audit_script_outputs_json_and_no_errors(self) -> None:
    proc = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
    payload = json.loads(proc.stdout)
    self.assertTrue(payload["success"])
    self.assertEqual(payload["summary"]["findings"]["error"], 0)
    self.assertEqual(payload["summary"]["findings"]["warning"], 0)
    self.assertGreaterEqual(payload["summary"]["skills_checked"], 10)

def test_audit_inventory_covers_handoff_matrix(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    matrix = payload["inventory"]["handoff_matrix"]

    self.assertEqual(len(matrix), len(audit.EXPECTED_PIPELINE_SKILLS) - 1)
    self.assertEqual(
        [(edge["from"], edge["to"]) for edge in matrix],
        list(zip(audit.EXPECTED_PIPELINE_SKILLS, audit.EXPECTED_PIPELINE_SKILLS[1:])),
    )
    self.assertTrue(all(edge["complete"] for edge in matrix))

def test_data_export_to_data_profile_handoff_has_required_contract_tokens(self) -> None:
    audit = _load_audit_module()
    matrix = audit.build_handoff_matrix()
    edge = next(item for item in matrix if item["from"] == "data-export" and item["to"] == "data-profile")

    checks = edge["checks"]
    self.assertTrue(checks["producer_outputs"]["found"])
    self.assertTrue(checks["consumer_inputs"]["found"])
    self.assertTrue(checks["trigger_or_next_step"]["found"])
    self.assertTrue(checks["state_update"]["found"])
    self.assertIn(["export_summary"], [item["tokens"] for item in checks["producer_outputs"]["token_groups"]])
    self.assertIn(["duckdb_export_summary.json"], [item["tokens"] for item in checks["consumer_inputs"]["token_groups"]])
    self.assertIn(["RA:data-profile"], [item["tokens"] for item in checks["trigger_or_next_step"]["token_groups"]])
    self.assertIn(["job_manifest 更新"], [item["tokens"] for item in checks["state_update"]["token_groups"]])

def test_report_to_report_verify_handoff_has_required_contract_tokens(self) -> None:
    audit = _load_audit_module()
    matrix = audit.build_handoff_matrix()
    edge = next(item for item in matrix if item["from"] == "report" and item["to"] == "report-verify")

    checks = edge["checks"]
    self.assertTrue(checks["producer_outputs"]["found"])
    self.assertTrue(checks["consumer_inputs"]["found"])
    self.assertTrue(checks["trigger_or_next_step"]["found"])
    self.assertTrue(checks["state_update"]["found"])
    self.assertIn(["输出文件清单"], [item["tokens"] for item in checks["producer_outputs"]["token_groups"]])
    self.assertIn(["report_md"], [item["tokens"] for item in checks["consumer_inputs"]["token_groups"]])
    self.assertIn(["RA:report-verify"], [item["tokens"] for item in checks["trigger_or_next_step"]["token_groups"]])
    self.assertIn(["verification.json"], [item["tokens"] for item in checks["state_update"]["token_groups"]])

def test_audit_inventory_covers_code_files_and_internal_script_candidates(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    code_files = payload["inventory"]["code_files"]

    self.assertGreaterEqual(code_files["python_file_count"], 50)
    self.assertGreaterEqual(code_files["test_file_count"], 10)
    self.assertIn("runtime/job_manifest.py", code_files["runtime_files"])
    self.assertIn("scripts/audit_project_contracts.py", code_files["project_scripts"])
    self.assertIn("tests/test_project_contract_audit.py", code_files["test_files"])
    self.assertIn("skills/metadata/adapters/tableau/scripts/test_views.py", code_files["manual_smoke_scripts_outside_tests"])
    self.assertIn("skills/data-export/scripts/sql/common_sql_export.py", code_files["potentially_internal_or_unreferenced_skill_scripts"])
    self.assertIn("test.sh", code_files["shell_entrypoints"])

def test_project_audit_report_lists_internal_script_candidates(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    candidates = payload["inventory"]["code_files"]["potentially_internal_or_unreferenced_skill_scripts"]
    report = (REPO / "tests" / "reports" / "2026-06-18-project-audit-gates.md").read_text(encoding="utf-8")

    self.assertGreaterEqual(len(candidates), 20)
    for script_path in candidates:
        self.assertIn(script_path, report)
```

## 7.1 内部/辅助脚本候选清单

以下脚本当前未被对应 `SKILL.md` / `README.md` 直接提到，审计将其列为 `potentially_internal_or_unreferenced_skill_scripts`。这不是自动判定为错误；它们可能是内部 helper、兼容入口、旧 adapter、手动维护脚本或待收敛代码。后续调整时必须逐项判断：保留并补文档、迁入正式入口、标注内部用途，或删除。

- `skills/analysis-run/scripts/cleanup_job_csvs.py`
- `skills/analysis-run/scripts/cleanup_temp_csvs.py`
- `skills/analysis-run/scripts/new_session_id.py`
- `skills/analysis-run/scripts/validate_analysis.py`
- `skills/data-export/scripts/sql/common_sql_export.py`
- `skills/data-export/scripts/tableau/_bootstrap.py`
- `skills/data-export/scripts/tableau/auth.py`
- `skills/data-export/scripts/tableau/build_tableau_report_dashboard.py`
- `skills/data-export/scripts/tableau/export.py`
- `skills/data-export/scripts/tableau/list.py`
- `skills/data-export/scripts/tableau/tableau_enrich_runtime_metadata.py`
- `skills/metadata-refine/scripts/_common.py`
- `skills/metadata-report/scripts/_bootstrap.py`
- `skills/metadata-report/scripts/dataset_report.py`
- `skills/metadata-report/scripts/duckdb_report.py`
- `skills/metadata-report/scripts/report_context.py`
- `skills/metadata-report/scripts/tableau_report.py`
- `skills/metadata-search/scripts/_bootstrap.py`
- `skills/metadata/scripts/_bootstrap.py`
- `skills/metadata/scripts/build_catalog.py`
- `skills/metadata/scripts/build_context.py`
- `skills/metadata/scripts/build_index.py`
- `skills/metadata/scripts/build_inventory.py`
- `skills/metadata/scripts/enrich_definitions.py`
- `skills/metadata/scripts/export_osi.py`
- `skills/metadata/scripts/init_metadata.py`
- `skills/metadata/scripts/metadata_audit.py`
- `skills/metadata/scripts/profile_review.py`
- `skills/metadata/scripts/read_metadata.py`
- `skills/metadata/scripts/reconcile_metadata.py`
- `skills/metadata/scripts/search_metadata.py`
- `skills/metadata/scripts/status_registry.py`
- `skills/metadata/scripts/sync_registry.py`
- `skills/metadata/scripts/validate_metadata.py`
- `skills/metadata/scripts/write_review_gap_report.py`

当前判定：这些是“需继续收敛的候选清单”，不作为本轮阻塞项；但它们已经进入测试报告和审计测试，后续增删必须同步解释。

## 8. 复跑命令

```bash
python3 scripts/audit_project_contracts.py
python3 -m unittest tests.test_project_contract_audit
python3 scripts/run_manifest_workflow_regression.py
bash test.sh
```

## 9. 实际结果

- 已通过：`python3 scripts/audit_project_contracts.py`，检查 15 个 Skill、9 个 schema、1 个 dataset 文件，error/warning 均为 0；输出包含 Skill inventory、每个 Skill 的脚本和 references、代码文件 inventory、metadata 文件清单与 counts、source evidence 清单、核心交付链和 handoff matrix。
- 已修复并验证：`metadata/dictionaries/demo.retail.dictionary.yaml` 原本引用 `metadata/sources/demo.md`，审计升级后发现该 evidence 文件缺失；已补 `metadata/sources/demo.md` 并通过 `metadata_source_evidence` 检查。
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，11 个测试覆盖 JSON 输出、0 warning、`test.sh` 接入、RA skill 前缀、pytest 收集边界、Skill 脚本 inventory、代码文件 inventory、metadata model/mapping/dictionary/source 引用完整性、metadata counts、完整 handoff matrix，以及 `data-export -> data-profile`、`report -> report-verify` 两条关键链路的 outputs / inputs / next step / state tokens。
- 已通过：`python3 scripts/run_manifest_workflow_regression.py`，`39 passed, 9 subtests passed`。
- 已通过：`bash test.sh`，包含 plugin manifest JSON、metadata validate、项目契约审计、CI workflow unittest、全仓 unittest discover（97 个测试）、manifest workflow regression（39 个 focused tests + 9 个 subtests）和 `git diff --check`。

## 10. 验收结论

本轮脚本化审计入口阶段性验收通过：已建立可复跑的项目契约审计脚本、对应单元测试，并接入 `test.sh` 与 focused regression。它证明当前基础结构、Skill 文档/代码入口 inventory、metadata 引用关系和核心交付链已有可复查门禁；更深层的业务 bug、跨 Skill 运行时交付断点和 metadata 脏内容仍需要后续按审计结果与专项测试继续扩展，不声明全项目总目标完成。

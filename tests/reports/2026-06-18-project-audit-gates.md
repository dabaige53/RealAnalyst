# 测试需求报告：全项目 Skills / 代码 / metadata 交付链审计

## 1. 背景

当前目标是对 RealAnalyst 的所有 Skills、代码、Skill 交付链和 metadata 资产做系统校验，找出介绍信息与代码不一致、代码缺陷、交付物断档、未使用文件、脏内容和复跑测试缺口。这个范围不能只靠一次人工阅读，需要沉淀成可重复运行的审计脚本和测试报告。

## 2. 目标行为

- 每个 `skills/*/SKILL.md` 的介绍信息、README、脚本目录、references 目录之间有基础一致性检查。
- 每个 Skill 声明的脚本、references、交付物契约能被脚本化审计到，不只靠人工记忆；审计 inventory 要列出每个 Skill 的脚本和 reference 文件。
- 核心交付链 `getting-started -> metadata -> analysis-run -> analysis-plan -> data-export -> data-profile -> report -> report-verify` 的相邻 handoff 必须被脚本化审计；每条相邻链路都要验证 producer outputs、consumer inputs、trigger/next step 和 state update 能在对应 Skill 文档中找到。
- 审计 JSON 必须输出 Skill inventory、代码文件 inventory、metadata 文件清单和核心交付链顺序，方便后续排查 Skill 介绍、代码入口和交付物是否断档。
- 代码文件 inventory 必须覆盖 Python 文件、自动测试、runtime 文件、project scripts、Skill scripts、未被 Skill/README 直接提到但可能属于内部 helper 的脚本、手动 smoke 脚本。
- 每个 Python 文件必须进入 `code_file_coverage` 覆盖策略，并绑定测试文件与测试报告；平台集成脚本、metadata adapter 脚本、Trellis/Codex/Claude 支撑脚本也不能遗漏。
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
assert "skills/data-export/scripts/sql/common_sql_export.py" in code_files["mentioned_skill_scripts"]

coverage = code_files["code_file_coverage"]
assert len(coverage) == code_files["python_file_count"]
assert not [item for item in coverage if item["category"] == "unclassified"]
for item in coverage:
    assert item["test_paths"], item["path"]
    assert item["report_paths"], item["path"]
    for path in item["test_paths"] + item["report_paths"]:
        assert (repo / path).exists(), (item["path"], path)

categories = {item["category"] for item in coverage}
assert "metadata_adapter_script" in categories
assert "platform_integration_support" in categories
assert "trellis_runtime_support" in categories

metadata_files = payload["inventory"]["metadata_files"]
assert metadata_files["counts"]["sync_reports"] >= 1
assert metadata_files["counts"]["generated_index"] >= 1

# 闭合不变量：每个 skill 脚本都已在其 SKILL.md / README 问责，无未问责脚本
assert code_files["potentially_internal_or_unreferenced_skill_scripts"] == []
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
    self.assertIn("skills/data-export/scripts/sql/common_sql_export.py", code_files["mentioned_skill_scripts"])
    self.assertIn("test.sh", code_files["shell_entrypoints"])

def test_no_unaccounted_skill_scripts(self) -> None:
    audit = _load_audit_module()
    payload = audit.run_audit()
    candidates = payload["inventory"]["code_files"]["potentially_internal_or_unreferenced_skill_scripts"]
    report = (REPO / "tests" / "reports" / "2026-06-18-project-audit-gates.md").read_text(encoding="utf-8")

    self.assertEqual(candidates, [], f"unaccounted skill scripts: {candidates}")
    for script_path in candidates:
        self.assertIn(script_path, report)

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

## 7.1 内部/辅助脚本问责（已收敛为 0）

审计字段 `potentially_internal_or_unreferenced_skill_scripts` 列出未被对应 `SKILL.md` / `README.md` 提到的 skill 脚本。早期该清单有 35 项（内部 helper、统一 CLI 背后的实现模块、兼容入口、维护工具等）。

本轮已把这 35 个脚本全部在各自 skill 的 `README.md` 增设的“脚本清单 / 内部脚本”小节中问责（标注其角色：入口 / 统一 CLI 子命令实现 / 内部模块），脚本被各自 README 提及后即脱离未问责清单。当前 `potentially_internal_or_unreferenced_skill_scripts` 长度为 **0**。

问责落点：

| Skill | README 小节 | 覆盖脚本 |
| --- | --- | --- |
| `metadata` | 脚本清单 | `metadata.py` 子命令实现（`build_index.py` / `validate_metadata.py` / `search_metadata.py` 等 15 个）+ `_bootstrap.py` + `write_review_gap_report.py` |
| `data-export` | 内部脚本 | `sql/common_sql_export.py` + `tableau/` 下 `auth.py` / `export.py` / `list.py` / `_bootstrap.py` / `build_tableau_report_dashboard.py` / `tableau_enrich_runtime_metadata.py` |
| `metadata-report` | 内部脚本 | `generate_report.py` 背后的 `report_context.py` / `dataset_report.py` / `duckdb_report.py` / `tableau_report.py` / `_bootstrap.py` |
| `analysis-run` | 内部脚本 | `new_session_id.py` / `validate_analysis.py` / `cleanup_temp_csvs.py` / `cleanup_job_csvs.py` |
| `metadata-refine` | 内部脚本 | `_common.py` |
| `metadata-search` | 内部脚本 | `_bootstrap.py` |

闭合不变量：`tests/test_project_contract_audit.py::test_no_unaccounted_skill_scripts` 断言该清单恒为 0——后续新增 skill 脚本若不在 SKILL.md/README 问责，审计与该测试会直接失败。

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
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，14 个测试覆盖 JSON 输出、0 warning、`test.sh` 接入、RA skill 前缀、pytest 收集边界、Skill 脚本 inventory、代码文件 inventory、每个 Python 文件的覆盖策略、metadata model/mapping/dictionary/source 引用完整性、metadata counts、完整 handoff matrix，以及 `data-export -> data-profile`、`report -> report-verify` 两条关键链路的 outputs / inputs / next step / state tokens。
- 已收敛：35 个未问责 skill 脚本已在各自 README 问责，`potentially_internal_or_unreferenced_skill_scripts` 长度为 0；`test_no_unaccounted_skill_scripts` 把“0 未问责”固化为闭合不变量。
- 已通过：`python3 scripts/run_manifest_workflow_regression.py`，`43 passed, 9 subtests passed`。
- 已通过：`bash test.sh`，包含 plugin manifest JSON、metadata validate、metadata index、项目契约审计、CI workflow unittest、全仓 unittest discover（104 个测试）、manifest workflow regression（43 个 focused tests + 9 个 subtests）和 `git diff --check`。

## 10. 验收结论

本轮脚本化审计入口阶段性验收通过：已建立可复跑的项目契约审计脚本、对应单元测试，并接入 `test.sh` 与 focused regression。它证明当前基础结构、Skill 文档/代码入口 inventory、metadata 引用关系和核心交付链已有可复查门禁；更深层的业务 bug、跨 Skill 运行时交付断点和 metadata 脏内容仍需要后续按审计结果与专项测试继续扩展，不声明全项目总目标完成。

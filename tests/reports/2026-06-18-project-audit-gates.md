# 测试需求报告：全项目 Skills / 代码 / metadata 交付链审计

## 1. 背景

当前目标是对 RealAnalyst 的所有 Skills、代码、Skill 交付链和 metadata 资产做系统校验，找出介绍信息与代码不一致、代码缺陷、交付物断档、未使用文件、脏内容和复跑测试缺口。这个范围不能只靠一次人工阅读，需要沉淀成可重复运行的审计脚本和测试报告。

## 2. 目标行为

- 每个 `skills/*/SKILL.md` 的介绍信息、README、脚本目录、references 目录之间有基础一致性检查。
- 每个 Skill 声明的脚本、references、交付物契约能被脚本化审计到，不只靠人工记忆；审计 inventory 要列出每个 Skill 的脚本和 reference 文件。
- 核心交付链 `getting-started -> metadata -> analysis-run -> analysis-plan -> data-export -> data-profile -> report -> report-verify` 的相邻 handoff 必须被脚本化审计；每条相邻链路都要验证 producer outputs、consumer inputs、trigger/next step 和 state update 能在对应 Skill 文档中找到。
- 审计 JSON 必须输出 Skill inventory、metadata 文件清单和核心交付链顺序，方便后续排查 Skill 介绍、代码入口和交付物是否断档。
- metadata 目录中不应出现明显分层污染、生成层手工内容、断裂 source evidence、未被入口引用的脏文件或旧报告冒充真源。
- 代码审计至少覆盖 Python 语法、测试收集、核心回归、schema JSON、CI workflow 与 `test.sh` 一致性。
- 审计输出是结构化 JSON，并能作为后续修复任务的输入。

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
```

## 8. 复跑命令

```bash
python3 scripts/audit_project_contracts.py
python3 -m unittest tests.test_project_contract_audit
python3 scripts/run_manifest_workflow_regression.py
bash test.sh
```

## 9. 实际结果

- 已通过：`python3 scripts/audit_project_contracts.py`，检查 15 个 Skill、9 个 schema、1 个 dataset 文件，error/warning 均为 0；输出包含 Skill inventory、每个 Skill 的脚本和 references、metadata 文件清单、source evidence 清单、核心交付链和 handoff matrix。
- 已修复并验证：`metadata/dictionaries/demo.retail.dictionary.yaml` 原本引用 `metadata/sources/demo.md`，审计升级后发现该 evidence 文件缺失；已补 `metadata/sources/demo.md` 并通过 `metadata_source_evidence` 检查。
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，10 个测试覆盖 JSON 输出、0 warning、`test.sh` 接入、RA skill 前缀、pytest 收集边界、Skill 脚本 inventory、metadata model/mapping/dictionary/source 引用完整性、完整 handoff matrix，以及 `data-export -> data-profile`、`report -> report-verify` 两条关键链路的 outputs / inputs / next step / state tokens。
- 已通过：`python3 scripts/run_manifest_workflow_regression.py`，`35 passed, 9 subtests passed`。
- 已通过：`bash test.sh`，包含 plugin manifest JSON、metadata validate、项目契约审计、CI workflow unittest、全仓 unittest discover（93 个测试）、manifest workflow regression（35 个 focused tests + 9 个 subtests）和 `git diff --check`。

## 10. 验收结论

本轮脚本化审计入口阶段性验收通过：已建立可复跑的项目契约审计脚本、对应单元测试，并接入 `test.sh` 与 focused regression。它证明当前基础结构、Skill 文档/代码入口 inventory、metadata 引用关系和核心交付链已有可复查门禁；更深层的业务 bug、跨 Skill 运行时交付断点和 metadata 脏内容仍需要后续按审计结果与专项测试继续扩展，不声明全项目总目标完成。

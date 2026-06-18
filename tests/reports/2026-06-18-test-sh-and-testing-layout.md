# 测试需求报告：test.sh 与测试文档目录收口

## 1. 背景

项目当前已有 `tests/` 自动化测试目录，同时新增过 `Test/` 测试文档目录，容易形成两个 test 文件夹并混淆“代码测试”和“测试报告文档”。本次调整要新增根目录 `test.sh` 作为一键测试入口，并把测试文档统一放入 `tests/reports/`。

## 2. 目标行为

- 根目录提供 `test.sh`，本地和 CI 可复用同一组公开测试命令。
- 代码自动化测试只放在 `tests/`。
- 测试需求报告、排查记录、复跑材料只放在 `tests/reports/`，测试文档规范写在 `tests/README.md`。
- `AGENTS.md` 明确全 Python 测试优先，避免后续重复创建 `Test/`、`test/` 或其它测试文档目录。

## 3. 风险等级

- 等级：P1
- 理由：测试入口和文档目录如果分裂，会导致 CI、本地复跑和 agent 交接依据不一致，后续排查难以重复。

## 4. 覆盖范围

- 涉及文件：`test.sh`、`.github/workflows/ci.yml`、`tests/test_ci_workflows.py`、`AGENTS.md`、`tests/README.md`。
- 涉及入口：本地一键测试、GitHub Actions public checks、测试文档规范。
- 不覆盖范围：不新增业务逻辑测试，不修复 manifest/report-verify 等已发现业务 bug。

## 5. Fixture / 环境前提

- Python：项目 CI 使用 Python 3.11；本地脚本默认使用 `python3`，可通过 `PYTHON=...` 覆盖。
- 依赖：调用者应先安装 `requirements.txt`；CI 仍负责安装依赖。
- 数据：只使用公开仓库内 demo metadata 和测试 fixture，不读取真实私有 job 数据。

## 6. 完整 Python 复现代码

```python
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
assert (repo / "test.sh").is_file()
assert (repo / "tests").is_dir()
assert (repo / "tests" / "README.md").is_file()
assert (repo / "tests" / "reports").is_dir()
assert not (repo / "Test").exists()
assert not (repo / "test").is_dir()
```

## 7. 完整 Python 测试代码

```python
def test_test_sh_runs_public_unit_and_manifest_regression_gates(self) -> None:
    script = TEST_SH.read_text(encoding="utf-8")

    expected_order = [
        "-m json.tool .codex-plugin/plugin.json",
        "skills/metadata/scripts/metadata.py validate",
        "scripts/audit_project_contracts.py",
        "-m unittest tests.test_ci_workflows",
        "-m unittest discover -s tests",
        "scripts/run_manifest_workflow_regression.py",
        "git diff --check",
    ]
    positions = []
    for token in expected_order:
        self.assertIn(token, script)
        positions.append(script.index(token))
    self.assertEqual(positions, sorted(positions))
```

## 8. 复跑命令

```bash
bash test.sh
python3 -m unittest tests.test_ci_workflows
git diff --check
```

## 9. 实际结果

- 已通过：`bash test.sh`。
- 覆盖命令：plugin manifest JSON 校验、metadata validate、project contract audit、CI workflow unittest、全仓 unittest discover、manifest workflow regression、`git diff --check`。
- 实际结果：`python3 -m unittest discover -s tests` 为 `Ran 91 tests ... OK`；`python3 scripts/run_manifest_workflow_regression.py` 为 `33 passed, 9 subtests passed`。
- 未通过：无。
- 未运行：未运行 Node/Playwright/浏览器测试；本次没有前端、浏览器或 Node 运行时变更。
- 备注：`unittest discover` 输出了两个 sqlite connection 的 `ResourceWarning`，不影响本次测试入口验收；后续可以单独清理资源关闭问题。

## 10. 验收结论

本次验收通过：`bash test.sh` 成功，CI workflow 调用同一入口，代码测试目录保留为 `tests/`，测试需求报告与复跑材料收口到 `tests/reports/`，仓库不再保留顶层 `Test/` 目录。

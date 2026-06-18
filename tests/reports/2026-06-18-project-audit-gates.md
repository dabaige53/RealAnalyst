# 测试需求报告：全项目 Skills / 代码 / metadata 交付链审计

## 1. 背景

当前目标是对 RealAnalyst 的所有 Skills、代码、Skill 交付链和 metadata 资产做系统校验，找出介绍信息与代码不一致、代码缺陷、交付物断档、未使用文件、脏内容和复跑测试缺口。这个范围不能只靠一次人工阅读，需要沉淀成可重复运行的审计脚本和测试报告。

## 2. 目标行为

- 每个 `skills/*/SKILL.md` 的介绍信息、README、脚本目录、references 目录之间有基础一致性检查。
- 每个 Skill 声明的脚本、references、交付物契约能被脚本化审计到，不只靠人工记忆。
- 审计 JSON 必须输出 Skill inventory、metadata 文件清单和核心交付链顺序，方便后续排查 Skill 介绍、代码入口和交付物是否断档。
- metadata 目录中不应出现明显分层污染、生成层手工内容、未被入口引用的脏文件或旧报告冒充真源。
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

## 6. 完整 JS 代码

```text
本次未使用 JS。原因：RealAnalyst 当前主体是 Python CLI、Markdown/YAML/JSON 契约、metadata 文件和 Codex skill 工作流；审计目标不是浏览器渲染、Node 包或前端交互。Python 能直接复用项目路径、schema、YAML/JSON parser 和现有测试入口。
替代复跑方式：python3 scripts/audit_project_contracts.py
```

## 7. 完整 JS 测试代码

```text
本次未使用 JS 测试。原因：项目没有 Node package 或前端测试 harness；CI workflow 和项目审计入口使用 Python unittest/pytest 覆盖更贴合真实 source of truth。
替代测试：python3 -m unittest tests.test_project_contract_audit
```

## 8. 复跑命令

```bash
python3 scripts/audit_project_contracts.py
python3 -m unittest tests.test_project_contract_audit
python3 scripts/run_manifest_workflow_regression.py
bash test.sh
```

## 9. 实际结果

- 已通过：`python3 scripts/audit_project_contracts.py`，检查 15 个 Skill、9 个 schema、1 个 dataset 文件，error/warning 均为 0；输出包含 Skill inventory、metadata 文件清单和核心交付链。
- 已通过：`python3 -m unittest tests.test_project_contract_audit`，5 个测试覆盖 JSON 输出、0 warning、`test.sh` 接入、RA skill 前缀、pytest 收集边界和 `data-export` 交付链契约。
- 已通过：`python3 scripts/run_manifest_workflow_regression.py`，覆盖 manifest 工作流 focused regression。
- 已通过：`bash test.sh`，包括 plugin manifest JSON、metadata validate、项目契约审计、全仓 unittest discover（86 个测试）、manifest workflow regression（32 个 focused tests + 9 个 subtests）。

## 10. 验收结论

本轮脚本化审计入口验收通过：已建立可复跑的项目契约审计脚本、对应单元测试，并接入 `test.sh` 与 focused regression。它证明当前基础结构没有发现硬错误，并且核心交付链已经有可复查 inventory；更深层的业务 bug、交付链断点和 metadata 脏内容仍需要后续按审计结果与专项测试继续扩展，不声明全项目总目标完成。

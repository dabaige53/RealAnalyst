# 测试需求报告：test.sh 与测试文档目录收口

## 1. 背景

项目当前已有 `tests/` 自动化测试目录，同时新增过 `Test/` 测试文档目录，容易形成两个 test 文件夹并混淆“代码测试”和“测试报告文档”。本次调整要新增根目录 `test.sh` 作为一键测试入口，并把测试文档统一放入 `docs/testing/`。

## 2. 目标行为

- 根目录提供 `test.sh`，本地和 CI 可复用同一组公开测试命令。
- 代码自动化测试只放在 `tests/`。
- 测试需求报告、排查记录、复跑材料只放在 `docs/testing/`。
- `AGENTS.md` 明确 Python/JS 测试边界，避免后续重复创建 `Test/`、`test/` 或其它测试文档目录。

## 3. 风险等级

- 等级：P1
- 理由：测试入口和文档目录如果分裂，会导致 CI、本地复跑和 agent 交接依据不一致，后续排查难以重复。

## 4. 覆盖范围

- 涉及文件：`test.sh`、`.github/workflows/ci.yml`、`tests/test_ci_workflows.py`、`AGENTS.md`、`docs/testing/README.md`。
- 涉及入口：本地一键测试、GitHub Actions public checks、测试文档规范。
- 不覆盖范围：不新增业务逻辑测试，不修复 manifest/report-verify 等已发现业务 bug。

## 5. Fixture / 环境前提

- Python：项目 CI 使用 Python 3.11；本地脚本默认使用 `python3`，可通过 `PYTHON=...` 覆盖。
- 依赖：调用者应先安装 `requirements.txt`；CI 仍负责安装依赖。
- 数据：只使用公开仓库内 demo metadata 和测试 fixture，不读取真实私有 job 数据。

## 6. 完整 JS 代码

```text
本次未使用 JS。原因：当前 RealAnalyst 主体是 Python CLI、schema、skill 和 metadata 工作流；本次调整的是 shell 一键测试入口与 Python/unittest/pytest 回归门禁。JS 不适合作为默认测试语言。
替代复跑方式：bash test.sh
```

## 7. 完整 JS 测试代码

```text
本次未使用 JS 测试。原因：CI workflow 与 test.sh 的契约已有 Python unittest 覆盖，项目没有 Node package 或前端运行时作为本次变更对象。
替代测试：python3 -m unittest tests.test_ci_workflows
```

## 8. 复跑命令

```bash
bash test.sh
python3 -m unittest tests.test_ci_workflows
git diff --check
```

## 9. 实际结果

- 已通过：待修复完成后填写。
- 未通过：待修复完成后填写。
- 未运行：待修复完成后填写。

## 10. 验收结论

本次验收以 `bash test.sh` 成功、CI workflow 调用同一入口、仓库不存在顶层 `Test/` 目录为准。

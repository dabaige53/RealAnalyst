# 测试文档规范

本目录保存排查、调整和修复前后的复跑材料。凡是 bug 排查、流程调整、输出契约调整、CI/回归门禁调整，都应在最终修复前新增或更新一份测试文档。

自动化代码测试也统一放在本目录：Python 测试文件使用 `tests/test_*.py` 命名；排查、复跑和测试需求报告放在 `tests/reports/*.md`。不要再创建 `Test/`、`test/`、`docs/testing/` 或其它第二套测试目录。

当前项目主体是 Python CLI、schema、metadata、runtime registry 和 Codex skill 工作流，默认全部使用 Python 测试，包括 `unittest`、`pytest` 和脚本 smoke。JavaScript 只在未来任务真实修改 Node、Playwright、Browser/Chrome 自动化、前端交互或网页渲染时作为例外补充，不是默认测试要求。

## 命名

建议使用：

```text
tests/reports/YYYY-MM-DD-short-topic.md
```

例如：

```text
tests/reports/2026-06-18-manifest-fail-closed.md
```

## 必填内容

每份测试文档必须包含：

- 测试需求报告：背景、目标行为、风险等级、覆盖范围、环境前提、验收标准。
- 排查记录：真实 source of truth、发现的问题、失败路径、边界条件。
- 完整 Python 复现代码：贴可运行的最小复现、fixture 生成或脚本调用代码。
- 完整 Python 测试代码：贴新增或修改的 `unittest` / `pytest` 测试代码，不只贴片段。
- 例外说明：只有任务真实涉及 Node、Playwright、Browser/Chrome 自动化、前端交互或网页渲染时，才补充 JS 代码和 JS 测试代码。
- 复跑命令：依赖安装、输入 fixture、执行命令、预期输出、实际输出摘要。
- 修复验收：哪些测试已通过，哪些未跑，未跑原因和剩余风险。

## 推荐模板

以下结构可直接复制到新的测试文档中：

### 测试需求报告：[主题]

#### 1. 背景

说明这次排查或调整要解决什么问题，为什么需要测试文档复跑。

#### 2. 目标行为

- 目标行为 1
- 目标行为 2

#### 3. 风险等级

- 等级：P0 / P1 / P2
- 理由：

#### 4. 覆盖范围

- 涉及文件：
- 涉及入口：
- 不覆盖范围：

#### 5. Fixture / 环境前提

- 数据：
- 环境变量：
- 依赖：

#### 6. 完整 Python 复现代码

```python
# runnable Python reproduction code
```

#### 7. 完整 Python 测试代码

```python
# runnable unittest/pytest code
```

#### 8. 复跑命令

```bash
# commands
```

#### 9. 实际结果

- 已通过：
- 未通过：
- 未运行：

#### 10. 验收结论

说明是否满足修复前/修复后的验收标准，以及剩余风险。

## 注意事项

- 不写 token、cookie、真实凭证或完整私有数据。
- 不用 mock、dry-run、缓存或旧日志冒充已验证结果。
- 用户态输出问题必须包含泄漏反例和修复后的不泄漏验证。
- CI 或回归门禁问题必须写清本地命令和 CI 期望命令是否一致。

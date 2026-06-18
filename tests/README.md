# 测试文档规范

本目录保存排查、调整和修复前后的复跑材料。凡是 bug 排查、流程调整、输出契约调整、CI/回归门禁调整，都应在最终修复前新增或更新一份测试文档。

自动化代码测试也统一放在本目录：Python 测试文件使用 `tests/test_*.py` 命名；排查、复跑和测试需求报告放在 `tests/reports/*.md`。不要再创建 `Test/`、`test/`、`docs/testing/` 或其它第二套测试目录。

当前项目主体是 Python CLI、schema、metadata、runtime registry 和 Codex skill 工作流，推荐以 Python 测试为主，包括 `unittest`、`pytest` 和脚本 smoke。JavaScript 只用于浏览器、Playwright、Node、前端交互、网页渲染或 CI JS harness 是真实 source of truth 的场景。如果本次未使用 JS，测试报告必须写明原因，并列出实际替代测试命令。

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
- 完整 JS 代码：如果使用 JavaScript、Node、Playwright、Browser/Chrome 自动化或 CI JS harness，贴完整可运行代码。
- 完整 JS 测试代码：如果写了 JS 测试，贴完整测试文件或测试函数，不只贴片段。
- 未使用 JS 的说明：如果本次没有 JS，写明原因，并列出实际使用的 Python、shell、pytest、unittest 或其它复跑方式。
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

#### 6. 完整 JS 代码

如果本次未使用 JS，写：

```text
本次未使用 JS。原因：...
替代复跑方式：...
```

如果使用 JS，贴完整代码：

```javascript
// runnable JS reproduction code
```

#### 7. 完整 JS 测试代码

如果本次未使用 JS 测试，写：

```text
本次未使用 JS 测试。原因：...
替代测试：...
```

如果使用 JS 测试，贴完整测试代码：

```javascript
// runnable JS test code
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

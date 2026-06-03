# RealAnalyst x Data Analytics 适配

## 目标

让 RealAnalyst 兼容 Data Analytics 插件：由 RealAnalyst 把项目本地 metadata 导出为 Data Analytics 可识别的 semantic-layer 形态，同时不修改 Data Analytics 插件本身。

## 已知事实

- RealAnalyst 是 metadata-first 的分析系统，核心由 Metadata Core、Runtime Registry Core 和 Job Core 三部分组成。
- Data Analytics 是 source-backed 的分析插件，工作流会经过 user-context、source lanes、semantic layers、live verification，以及 report/dashboard 交付。
- Data Analytics 当前没有保存本地 source-routing 偏好，也没有注册 semantic layers。
- Data Analytics semantic layers 是本地 Codex skills，包含 source inventory、指标/表指导、限制说明、查询模式和 freshness 规则。
- RealAnalyst 已经具备 `metadata context`、`semantic_ref`、metadata search/index、runtime registry sync、OSI export、job artifacts 和 report verification。

## 需求

- 桥接能力由 RealAnalyst 负责，不通过修改 Data Analytics 实现。
- 保持 RealAnalyst 分层边界：metadata 是语义真源，runtime registry 是可执行 source 状态，jobs 是单次运行证据。
- 从已验证的 RealAnalyst metadata 生成 Data Analytics 兼容的 semantic-layer package。
- 选定方案是新增 `RA:data-analytics-semantic-export`，由该 skill 生成 Data Analytics semantic-layer 使用副本。
- semantic-layer 内容默认维护在全局 `$CODEX_HOME/skills/<area-slug>-semantic-layer/`，严格遵循 Data Analytics 的默认形态，不自动追加 RealAnalyst 或项目名前缀。
- Data Analytics 全局 `user-context` 只记录 semantic-layer 指针；默认不自动写入，除非后续另做显式注册能力且获得用户批准。
- RealAnalyst 项目内 `metadata/datasets`、`metadata/dictionaries`、`metadata/mappings`、`metadata/sources`、`metadata/audit`、`runtime/registry.db`、`jobs/` 仍是正式语义真源。
- 全局 semantic-layer 是从 RealAnalyst metadata 导出的使用副本 / 语义投影；如果与 RealAnalyst metadata 不一致，以 RealAnalyst metadata 为准。
- Data Analytics 仍然负责自己的实时 source 读取和 report/dashboard 渲染。
- 注册到 Data Analytics user-context 必须是显式操作，并需要用户批准。
- 生成的 semantic-layer 文件不得包含敏感数据、凭据、行级样例或较长的私有原文摘录。

## 语言要求

- 后续用户回复与交付材料默认使用简体中文。
- 文件路径、命令、函数名、配置键、skill 名、Data Analytics、semantic-layer、user-context、runtime registry、metadata context 等技术名词可保留英文或中英混排。
- 面向产品经理的说明应避免不必要的底层实现细节，优先说明边界、输入、输出、风险和验收方式。

## 推荐方案

构建一条 RealAnalyst semantic-layer 导出路径，新增 skill：`RA:data-analytics-semantic-export`。

该 skill 的职责是把 RealAnalyst metadata 投影为 Data Analytics semantic-layer skill package。它不注册 Data Analytics user-context，不修改 Data Analytics plugin，也不写回 RealAnalyst metadata。

导出结果应创建：

- `SKILL.md`：供 Data Analytics 使用的小型操作入口。
- `references/semantic-layer.md`：指标、粒度、筛选器、source objects、查询/导出模式、限制说明、freshness 规则和未决问题。
- `references/source-inventory.md`：已检查 sources、覆盖程度、权限状态、缺口和更新边界。
- MVP 不生成 `references/evidence.md`；仅当 provenance 内容过大、不适合放进 semantic-layer 文件时后续扩展。

生成来源包括 `metadata/dictionaries`、`metadata/mappings`、`metadata/datasets`、metadata context helper、runtime registry status，以及可选的 job/report evidence。导出文件必须包含字段映射、指标、字段/维度/筛选器、source objects、grain/time fields、caveats、open questions 和 provenance paths。

默认输出：

```text
$CODEX_HOME/skills/<area-slug>-semantic-layer/
```

如需避免同名冲突，必须由用户显式传入 `--skill-name`；本任务不自动创建额外命名前缀。

脚本 stdout 输出 JSON summary：`success`、`output_path`、`files_written`、`datasets`、`suggested_user_context_entry`、`data_analytics_validation_prompt`。测试使用 `--output-dir` 写临时目录，不写真实全局目录。

导出完成后的验收步骤必须包含 Data Analytics 独立检查：派一个独立子代理或独立检查 pass，显式加载 Data Analytics semantic-layer setup/template/source-intake 要求和生成 package，检查输入数据、字段映射、指标、source inventory、caveats、open questions、provenance 是否一致，并确认能被 Data Analytics 后续分析使用。导出脚本本身不启动子代理。

## 备选方案

| 方案 | 摘要 | 适配度 |
| --- | --- | --- |
| RealAnalyst semantic-layer 导出 | 生成 Data Analytics 兼容的本地 skill package | 最适合作为主桥接方案 |
| OSI 优先交换包 | 导出 OSI YAML 和 source inventory | 可作为辅助，但单独使用信息太薄 |
| Job 交接包 | 让 Data Analytics 消费已完成的 RealAnalyst job artifacts | 适合一次运行后的 report/dashboard 交接 |

## 不在范围内

- 修改 Data Analytics 插件代码、skill 文件、user-context 脚本或 MCP widgets。
- 把 RealAnalyst 做成 Data Analytics connector。
- 用 RealAnalyst reports 替代 Data Analytics 的 report/dashboard 工作流。
- 默认写入或修改 `$CODEX_HOME/state/plugins/data-analytics/user-context.md`。
- 未经明确批准写入 `$CODEX_HOME/state/plugins/data-analytics/`。
- 在本任务中真实生成全局 `$CODEX_HOME/skills/<skill-name>/` package；测试必须使用 `--output-dir`。
- 把生成的 semantic-layer 文件视为当前实时数据的证明。

## 验收标准

- [x] 已验证的 RealAnalyst dataset 可以生成 Data Analytics semantic-layer skill package。
- [x] 生成的 package 符合 Data Analytics 的 semantic-layer template。
- [x] package 包含 source 优先级、指标定义、粒度、source objects、filters、caveats、freshness 规则和未决问题。
- [x] package 包含字段映射：Data Analytics concept / display name、RealAnalyst 字段、physical field、source/backend/object、definition ref/status/caveat。
- [x] package 默认目标是 `$CODEX_HOME/skills/<area-slug>-semantic-layer/`，测试和本任务执行不写真实全局目录；如需自定义命名，必须显式传 `--skill-name`。
- [x] 注册到 Data Analytics user-context 与 package 生成分离。
- [x] 不修改任何 Data Analytics 插件文件。
- [x] RealAnalyst validation、index 和 runtime 边界保持完整。
- [x] 工作流包含 Data Analytics 子代理 / 独立检查 pass：加载 Data Analytics semantic-layer 要求和生成 package，确认输入数据、映射、指标、source inventory、caveats、open questions、provenance 可供后续分析使用。
- [x] 后续用户回复与交付材料默认使用简体中文的要求已写入任务材料。

## 研究参考

- `research/local-contracts.md`：RealAnalyst 与 Data Analytics 契约对比，以及桥接方案。

## 下一步决策

选择第一段实现切片：

1. 本任务只做 `RA:data-analytics-semantic-export` 和 deterministic package 生成器。
2. Data Analytics user-context 注册能力后续单独做，并且必须显式请求用户批准。
3. 本任务完成时不修改 Data Analytics plugin，不真实写全局 semantic-layer，不写 Data Analytics user-context。

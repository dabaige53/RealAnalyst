# Repository Layout

RealAnalyst 将 skills、元数据真源、connector 同步快照、生成物和本地运行状态分开管理。

| 路径 | 维护方 | Git 策略 | 作用 |
| --- | --- | --- | --- |
| `skills/` | 项目 | 跟踪 | Codex skills。 |
| `metadata/sources/` | LLM + reviewer | 只跟踪脱敏 example | 原始材料和审计证据。 |
| `metadata/dictionaries/` | LLM + reviewer | 只跟踪 demo/example | 公共指标、维度、术语。 |
| `metadata/mappings/` | LLM + reviewer | 只跟踪 demo/example | source 字段到标准语义的映射。 |
| `metadata/datasets/` | LLM + reviewer | 只跟踪 demo/example | 真实可分析数据源 metadata。 |
| `metadata/models/` | LLM + reviewer | 只跟踪 demo/example | 语义模型。 |
| `metadata/sync/` | connector 脚本 | 只跟踪 `.example.*` | 同步快照，给 LLM 整理 metadata 用。 |
| `metadata/index/` | 脚本生成 | 忽略 | 轻量检索索引。 |
| `metadata/osi/` | 脚本生成 | 忽略 | OSI export。 |
| `runtime/` | 项目 + 本地运行 | 跟踪代码和 example | 程序执行层。真实 DB 不上传。 |
| `config/` | 旧本地私有目录 | 忽略 | 不再作为公开仓库结构。 |
| `examples/` | 项目 | 跟踪 | 脱敏示例。 |
| `jobs/` | 运行时 | 忽略 | 单次分析任务产物。 |

首次使用应从 `/skill getting-started` 开始，先初始化 metadata，再进入分析。

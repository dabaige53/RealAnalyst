# Metadata Maintenance Contract

## 五层边界

| 层级 | 作用 | 是否用户维护 |
| --- | --- | --- |
| YAML | 数据集、字段、指标、术语、业务定义、证据、置信度、review 标记 | 是，由 LLM 维护 |
| index | 从 YAML 生成的轻量检索记录 | 否，自动生成 |
| context pack | 给分析规划读取的最小上下文 | 否，按需生成 |
| registry.db | 运行时 source 与执行配置 | 否，由 connector/runtime 流程维护 |
| OSI | 对外交换语义模型 | 否，按需导出 |

## 维护规则

- 业务口径只写入 YAML，不写入 index。
- index 只能由 YAML 生成，不能人工维护。
- context pack 只能用于本轮分析，不作为持久真源。
- `registry.db` 不接受 YAML 反写覆盖。
- OSI 只用于交换，不参与本地需求理解链路。
- `needs_review=true` 或 `review_required=true` 的定义必须被标记为推断口径。

## 原独立 skills 的合并关系

| 原 skill | 收敛后入口 |
| --- | --- |
| metadata-init | `metadata init` |
| metadata-validate | `metadata validate` |
| metadata-index | `metadata index` |
| metadata-search | `metadata search` |
| metadata-context | `metadata context` |
| metadata-inventory | `metadata inventory` |

这些能力仍然存在，但不再作为独立用户 skill 暴露。

## 当前阶段移出的能力

`registry-compile` 不作为当前阶段能力暴露，因为它会形成 YAML 到 `registry.db` 的第二条写入链。

`semantic-context-read` 不作为当前阶段能力暴露，因为本地分析统一使用 `metadata context`，避免出现两套 context pack。

`osi-export` 不作为独立用户 skill 暴露；OSI 导出并入 `metadata export-osi`，只作为交换导出能力保留，不进入需求理解、数据初始化或分析主路径。

## Review 规则

| 状态 | 分析中如何使用 |
| --- | --- |
| `needs_review=false` 且证据充分 | 可以作为确认口径候选 |
| `needs_review=true` | 只能作为推断口径 |
| 缺少证据 | 不能作为确定口径 |
| 低置信度但未标 review | 先修 YAML，再分析 |

报告和验证必须写明推断口径，不能把 review 状态藏在技术附录里。

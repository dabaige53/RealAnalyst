# Design — Skills 与元数据全量审计

## 审计方法论

分两层：

1. **复用自动化层（不重复）**：先跑 `test.sh` 各步与 `audit_project_contracts.py`，记录基线结论作为"已覆盖"清单。报告中这部分只做引用与差异说明，不重复列举。
2. **人工深度层（本次重点）**：对每个 Skill 做"文档 ↔ 代码 ↔ 交付物"三角核对，并对跨 Skill 链路做端到端追踪。

## 三角核对法（每个 Skill）

对每个 Skill 执行：

- **文档面**：解析 `SKILL.md` frontmatter（name/description）、声明的命令与脚本路径、引用的 `references/*`。
- **代码面**：列出 `scripts/`、`lib/` 实际文件与入口；核对 SKILL.md 里出现的每条命令/路径是否真实存在、参数是否匹配。
- **交付面**：确认 Skill 产出的 artifact（写到 `jobs/<id>/...` 或 manifest 的内容）与下游消费方约定一致。

三者不一致即为发现（drift）。

## 跨 Skill 链路追踪

以主链路为骨架，逐跳验证 producer 输出 → consumer 输入：

```
getting-started → metadata → analysis-run ↔ analysis-plan
   → data-export / data-profile → report → report-verify
   （旁支：metadata-search / metadata-refine / metadata-report / reference-lookup
     / analysis-reference / data-analytics-semantic-export / artifact-fusion）
```

复用 `audit_project_contracts.py` 中的 `HANDOFF_CONTRACTS` 与 `SKILL_DELIVERY_TOKENS` 作为已知契约基线，重点查：契约未声明但实际存在的衔接、声明了但代码未实现的衔接、孤儿产物（产出无人消费）。

## 元数据审计

- 遍历 `metadata/` 全部 YAML，构建"文件被谁引用"图谱，找孤儿文件与断链。
- 核对 `FORBIDDEN_DATASET_KEYS` 是否真的不出现在 dataset 层。
- 核对 `runtime/registry.db`、index 产物与源 YAML 的一致性（是否过期/脏）。

## 并行执行策略

按 Skill 分组用只读 Explore/general-purpose 子代理并行收集证据（每组返回结构化发现：维度/级别/file:line/建议），主代理负责跨 Skill 链路追踪与最终去重、定级、汇总成报告。子代理只读，不改代码。

## 报告结构（交付物）

`tests/reports/2026-06-19-skills-metadata-full-audit.md`：

1. 背景与基线（自动化层结论引用）
2. Skill × 维度覆盖矩阵
3. 按维度分章的发现（每条：维度/级别/证据/影响/修复建议）
4. 跨 Skill 链路断档分析
5. 元数据卡点/脏内容/孤儿文件清单
6. 测试覆盖缺口
7. 按严重级别排序的建议修复清单

## 定级标准

- **P0**：链路断裂导致主流程跑不通 / 文档命令直接报错 / 数据正确性问题。
- **P1**：契约漂移导致下游可能误用 / 无测试覆盖的核心实现面 / 脏数据进入交付。
- **P2**：文档与代码轻微不一致 / 孤儿文件 / 边界未处理但不影响主路径。
- **P3**：可读性、措辞、冗余等改进项。

## 兼容性 / 回滚

纯只读审计，无代码变更，无需回滚。报告文件可随时删除重写。

# Implement — Skills 与元数据全量审计执行计划

## 前置基线（only-once）

- [x] 执行 `bash test.sh` 全量回归，当前通过：metadata validate/index、项目契约审计、104 个 unittest、43 个 manifest workflow regression tests、9 个 subtest 和 `git diff --check`。
- [x] 保存 `audit_project_contracts.py` 输出的 inventory 作为"自动化已覆盖"基线。

## 阶段 A：逐 Skill 三角核对（可并行）

按 Skill 分批，对每个 Skill 收集发现（维度/级别/file:line/建议）：

- [x] A1. 数据/元数据入口组：`getting-started`, `metadata`, `metadata-search`, `metadata-refine`, `metadata-report`
- [x] A2. 分析编排组：`analysis-plan`, `analysis-reference`, `analysis-run`, `reference-lookup`
- [x] A3. 数据产出组：`data-profile`, `data-export`, `data-analytics-semantic-export`
- [x] A4. 报告组：`report`, `report-verify`, `artifact-fusion`

每个 Skill 核查清单：
- SKILL.md frontmatter 完整性（name/description/allowed-tools 等）
- SKILL.md 中每条命令/脚本路径在 `scripts/`、`lib/` 真实存在
- 命令参数、子命令与实现一致
- references/ 被 SKILL.md 引用且无断链
- 脚本代码问题（异常处理、路径假设、schema 校验、编码、时间/随机性）
- 该 Skill 产出 artifact 是否有测试覆盖

## 阶段 B：跨 Skill 链路追踪（主代理）

- [x] B1. 沿主链路逐跳验证 producer 输出 ↔ consumer 输入。
- [x] B2. 对照 `HANDOFF_CONTRACTS` / `SKILL_DELIVERY_TOKENS`，找声明缺失或代码未实现的衔接。
- [x] B3. 找孤儿产物（产出无人消费）与缺失衔接步骤。

## 阶段 C：元数据审计

- [x] C1. 遍历 `metadata/` YAML，建引用图谱，列孤儿文件与断链。
- [x] C2. 核对 `FORBIDDEN_DATASET_KEYS` 不出现在 dataset 层。
- [x] C3. 核对 index/registry 产物与源 YAML 一致性（过期/脏内容）。

## 阶段 D：测试覆盖缺口

- [x] D1. 用 `code_surface_matrix` + `code_file_coverage` 对照，列无专项测试的实现面。
- [x] D2. 列有交付物但无端到端测试的链路。

## 阶段 E：汇总成报告

- [x] E1. 去重、定级、归类到 6 维度。
- [x] E2. 生成 Skill × 维度覆盖矩阵。
- [x] E3. 写 `tests/reports/2026-06-19-skills-metadata-full-audit.md`。
- [x] E4. 生成按级别排序的建议修复清单。

## 验证命令

```bash
python3 scripts/audit_project_contracts.py      # 自动化契约层基线
python3 -m unittest tests.test_project_contract_audit
bash test.sh                                    # 已在最终 check 阶段全量通过
```

## 回滚点

纯只读审计，无代码变更。报告文件可删除重写，无回滚风险。

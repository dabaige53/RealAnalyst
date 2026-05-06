# Verification Check Rules

`verify.py` 执行 10 类检查，每类检查的判定标准如下。

## 检查项详解

### 1. `evidence_completeness`

**目标**：每条 `finding` 是否具备完整的证据链。

| 子检查 | 通过条件 | 状态 |
|---|---|---|
| `has_source_file` | `evidence.source_file` 存在且非空 | failed 若缺失 |
| `has_calculation` | `evidence.calculation` 存在且非空 | warning 若缺失 |
| `has_row_indices` | `evidence.row_indices` 存在且为非空列表 | warning 若缺失 |

### 2. `ranking_consistency`

**目标**：报告中声明的排名结论与 `statistics` 中的 `top_items` 一致。

- 从 `analysis.json` 的 `statistics[*].top_items` 提取排名顺序
- 从报告 Markdown 中提取 TopN 表格的第一列顺序
- 若报告中 Top1 与统计结果 Top1 不一致 → `failed`
- 若无法提取排名信息 → `warning`

### 3. `trend_consistency`

**目标**：报告中的趋势方向描述与 `statistics` 中的 `trend_label` 一致。

| 报告词 | 对应 trend_label | 不一致则 |
|---|---|---|
| 增长、上升、提升、改善 | `up` | `failed` |
| 下降、减少、恶化 | `down` | `failed` |
| 持平、稳定 | `flat` | `warning` |

### 4. `numeric_traceability`

**目标**：报告正文中的关键数字可追溯到 `analysis.json` 的 `findings` 或 `statistics`。

- 从报告中提取数字（百分比、绝对值、同比值）
- 在 `findings[*].value` 和 `statistics[*].total` 中匹配
- 匹配率 < 50% → `warning`；关键结论数字完全无法匹配 → `failed`

### 5. `confidence_threshold`

**目标**：低置信度 finding 不被当成确定结论。

- `confidence < 0.7` 的 finding 对应的报告结论必须标注为"推断口径"或"待确认"
- 若未标注 → `failed`

### 6. `metric_definition_appendix`

**目标**：报告包含 `## 口径说明（本次新增/临时）` 附录。

- 检查报告中是否存在该章节标题（精确或近似匹配）
- 缺失 → `warning`

### 7. `metric_term_consistency`

**目标**：不把子集指标静默写成总量指标。

- 检查 `source_context.json` 中标记为 `subset_scope` 的字段
- 若报告中对该字段使用了通用总量名称（未披露映射关系）→ `failed`

### 8. `data_source_section_position`

**目标**：`## 数据来源` 章节位于报告上方（前 30% 内容以内）。

- 若章节存在但位置靠后 → `warning`
- 若章节不存在 → `failed`

### 9. `data_source_display_name`

**目标**：数据来源展示使用中文业务名，不暴露英文 source_key。

- 检查 `## 数据来源` 章节内容是否包含英文 source_key 形式的标识符
- 若包含 → `warning`

### 10. `output_file_list_section`

**目标**：报告包含 `## 输出文件清单` 章节。

- 缺失 → `warning`

## 状态定义

| 状态 | 条件 |
|---|---|
| `passed` | 所有检查项通过 |
| `warning` | 无 failed，但有 warning 项，需人工复核 |
| `failed` | 存在 failed 项，禁止交付 |

## 未校验的 needs_review 口径

未标注为推断口径的 `needs_review=true` 指标不得作为确定口径通过 `confidence_threshold` 检查。

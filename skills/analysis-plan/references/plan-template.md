# Analysis Plan Template

输出路径固定为 `jobs/{SESSION_ID}/.meta/analysis_plan.md`。
# 分析规划

## 1. 需求解析
- **原始请求**: {用户原始请求}
- **任务类型**: {request_type}
- **业务目标**: {business_goal}
- **阅读对象**: {audience}
- **分析场景**: {识别的场景}
- **置信度**: 高/中/低

## 2. 参数确认
| 参数 | 值 | 来源 |
|------|-----|------|
| 分析对象 | {entity} | 用户请求/默认 |
| 时间范围 | {time_range} | 用户请求/默认 |
| 关注指标 | {metric} | 用户请求/默认 |
| 分析维度 | {dimension} | 数据识别 |

## 3. 数据源定位
```yaml
data_source:
  entry_type: A  # A=指定数据源, B=指标需求
  source_key: xxx
  source_backend: tableau  # 或 duckdb
  type: view/domain/duckdb_table/duckdb_view
  display_name: xxx
  locked: true
  limitations: []
```

## 4. 数据源元数据（MUST - 来自 source spec）

- **source_backend**: {tableau / duckdb}
- **推荐时间字段**: {字段名或无}
- **数据粒度（grain）**: {grain}

### 可用筛选维度 / 可用分析维度
| 维度 | 类型 | 适合下钻 | 示例值 |
|------|------|---------|--------|
| {维度1} | discrete/date_range/time_field | ✅/❌ | {sample_values} |

### 可用指标
| 指标 | 公式/类型 | 业务含义 |
|------|-----------|---------|
| {指标1} | {formula_or_field_type} | {description} |

### 维度-指标匹配检查
- 假设验证所需维度：{列表}
- 数据源是否支持：✅/❌（缺少：{列表}）

## 5. 业务假设（MUST）

### 假设 1: [假设内容]
- **类型**: [假设类型]
- **业务逻辑**: [为什么合理]
- **验证方法**: [如何验证]
- **验证指标**: [看什么指标] — **必须来自"可用指标"**
- **验证维度**: [按什么维度切分] — **必须来自"可用筛选维度"**

### 假设 2: ...
### 假设 3: ...

## 6. 异常判定标准（MUST）

| 指标 | 优秀 | 良好 | 正常 | 警告 | 来源 |
|------|------|------|------|------|------|
| {指标1} | {值} | {值} | {值} | {值} | metadata context / 用户确认 |

- **波动阈值**: {X}%
- **对比基准**: {同比/环比/预算}
- **选择理由**: {理由}

## 7. 下钻路径设计（MUST）

| 阶段 | 动作 | 使用维度 | 预期输出 | 触发条件 |
|------|------|---------|----------|----------|
| 1. 总量定位 | {动作} | — | {输出} | {条件} |
| 2. 结构下钻 | {动作} | {维度1→维度2} | {输出} | {条件} |
| 3. 因子归因 | {动作} | {维度3} | {输出} | {条件} |

**维度使用校验**：所有下钻维度必须存在于"可用筛选维度"中。

## 8. 分析框架
- **选用框架**: {框架名称}
- **选择理由**: {理由，必须关联假设}
- **logic_path 来源**: analysis-plan skill guidance / metadata context / 用户确认

## 9. 分析目标

### 固定目标
- [ ] goal-1: 明确分析范围与数据口径
- [ ] goal-2: 输出核心指标概览（参考 metadata context 中的核心指标）

### 假设验证目标（MUST）
- [ ] goal-hypo-1: 验证假设 1 - {假设内容简述}
- [ ] goal-hypo-2: 验证假设 2 - {假设内容简述}
- [ ] goal-hypo-3: 验证假设 3 - {假设内容简述}

### 维度目标
- [ ] goal-dim-{维度}: 按{维度}维度分析结构分布与 Top/Bottom
  - artifact: csv
  - filename: 汇总_{维度}_{time_range}.csv
  - params: { top_n: 20 }

### 交叉目标
- [ ] goal-cross-1: {维度1}×{维度2}交叉分析
  - artifact: csv
  - filename: 交叉_{维度1}×{维度2}_{time_range}.csv
- [ ] goal-cross-2: {维度1}×{维度2}交叉分析
  - artifact: csv
  - filename: 交叉_{维度1}×{维度2}_{time_range}.csv

### 总结目标
- [ ] goal-summary: 总结假设验证结果与关键发现

## 10. 预期输出
- **报告类型**: {模板名称}
- **selected_analysis_mode**: {overview / ranking / attribution / benchmark / exploration}
- **analysis_mode_selection_reason**: {为什么这次应该用这种分析方式}
- **selected_delivery_mode**: {executive_brief / structured_report / diagnosis_report / detailed_report}
- **delivery_mode_selection_reason**: {为什么这次适合这种呈现方式}
- **selected_report_template**: {core_template_id}
- **template_selection_reason**: {为什么这个核心模板最适合本次任务；若用户提到旧模板名，也要说明 alias 如何收敛到该核心模板}
- **核心章节**: {章节列表}
- **关键证据展示要求**:
  - {正文必须直接展示的数据块 1}
  - {正文必须直接展示的数据块 2}
  - {只保留在 CSV 中的明细数据}
- **结论级证据块设计**:
  - 关键结论 1：{结论摘要} → 紧贴展示 {问题对象/问题行/TopN表}
  - 关键结论 2：{结论摘要} → 紧贴展示 {问题对象/问题行/风险对象表}
  - 关键结论 3：{结论摘要} → 紧贴展示 {关键异常行/偏离对象}
- **预期洞察**: {基于假设的预期结论方向}

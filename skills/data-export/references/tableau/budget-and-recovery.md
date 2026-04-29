# 预算与恢复策略

## 预算限制

- 默认 `max_count = 5`
- 当前实现只统计成功导出
- 超限返回 `EXPORT_BUDGET_EXCEEDED`

## 降低调用次数

1. 一次导出完整业务范围
2. 用 domain 模式合并相关视图
3. 不要在循环里按碎片时间段重复导出

## 超限后的动作

1. 不再调用 tableau skill
2. 在报告开头补充数据限制说明
3. 列出已获取文件
4. 基于现有产物继续分析，不把“重新导出”当默认路径

## 恢复路径

只有以下情况才考虑恢复性导出：

- `export_summary.json` 缺失
- 清单中的正式文件不存在
- registry 无匹配或导出失败

恢复前先核对：

1. `export_summary.json`
2. `.meta/analysis_plan.md`
3. 现有 `data/` 目录文件

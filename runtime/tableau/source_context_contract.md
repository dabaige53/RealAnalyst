# Source Context Contract

## 目标

在查询数据源或导出数据源时，同步返回/落盘与该 source 关联的指标定义、维度定义、筛选条件和口径风险，减少分析阶段的隐式猜测。

## 当前入口

### 1. 查询数据源

```bash
./scripts/py runtime/tableau/query_registry.py --source <source_id> --with-context
```

返回内容新增：
- `source_context.metrics`
- `source_context.dimensions`
- `source_context.filters`
- `source_context.mapping_summary`
- `source_context.role_mismatches`

### 2. 导出数据源

```bash
./scripts/py skills/data-export/scripts/tableau/export_source.py --source-id <source_id> --session-id <SESSION_ID>
```

导出目录新增：
- `source_context.json`
- `context_injection.md`

`export_summary.json` 与 stdout JSON 新增：
- `source_context_path`
- `context_injection_path`

## 映射优先级

1. 显式映射：`runtime/tableau/source_context_mappings.yaml`
2. 标准库精确匹配：
   - 指标：`runtime/runtime_config.db -> metrics / metric_aliases`
   - 维度：`runtime/runtime_config.db -> dimensions / dimension_fields`
3. 无法精确匹配时：标记为 `unresolved`
4. 若 source 语义角色与标准库角色冲突：标记为 `role_mismatch`

## 输出状态

- `mapped`：已映射到标准定义
- `unresolved`：暂无可靠映射
- `role_mismatch`：当前角色疑似不符，例如 source 把字段列为维度，但标准库更像指标
- `ambiguous`：命中多个候选定义
- `override_error`：显式映射配置错误

## 设计原则

- 不静默猜测口径
- 不把子集指标自动上升为总口径
- 不把本期/上期/同比字段自动改写成通用指标名
- 可以通过 override 继承标准定义，并对当前 source 做 `definition_override / subset_scope / name_override`

## 后续建议

若要把上下文注入进一步做准，下一步优先补：
- 订单类 source 的 `订单数`、`收入`、`折扣金额`
- 产品类 source 的品类、SKU、渠道与区域维度
- 订阅类 source 的新增、续费、流失与留存口径

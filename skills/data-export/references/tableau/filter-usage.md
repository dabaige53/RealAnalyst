# 筛选器与参数使用

## 选择 `--vf` 还是 `--vp`

- `filters:` 中定义的离散筛选器，用 `--vf`
- `parameters:` 中定义的参数，用 `--vp`

## 推荐查询

```bash
python3 {baseDir}/runtime/tableau/query_registry.py --job-id $SESSION_ID --filter <source_key>
python3 {baseDir}/runtime/tableau/query_registry.py --job-id $SESSION_ID --fields <source_key>
```

## 常见示例

```bash
--vf "代理_区域=上海区域"
--vf "产品=PVG-NRT"
--vp "出票日期_开始=2025-10-01"
--vp "出票日期_结束=2025-12-31"
```

## 字段校验

导出前确认：

1. 字段存在于 `query_registry.py --filter <source_key>` 返回结果中
2. enum 字段的值没有超出允许范围
3. 枚举型筛选字段若支持逗号多值，可先合并筛选

## Fallback

本地筛选 fallback 的具体策略见 `filters-fallback.md`。只有筛选器不可用或格式未知时才进入 fallback。

# 导出命名与调用方式

## 推荐模式：`export_source.py`

```bash
python3 {baseDir}/skills/data-export/scripts/tableau/export_source.py --source-id tableau.sales.ai__ \
  --vf "代理_区域=上海区域"
```

推荐模式会自动使用 `$SESSION_ID` 推导输出目录，并生成：

- `data/交叉_{source_key}.csv`
- `export_summary.json`
- `profile/manifest_{tag}.json`（export validation artifact，不是 `RA:data-profile` 的正式 `profile/manifest.json`）
- `profile/assertions_{tag}.json`（export validation artifact，不是 `RA:data-profile` 的正式 `profile/profile.json`）

正式画像产物只由 `RA:data-profile` 生成：`profile/manifest.json` 和 `profile/profile.json`。上述 `{tag}` 文件保留为 Tableau 导出阶段的兼容校验材料，后续可迁移到 validation/export 目录。

## Domain 模式

```bash
python3 {baseDir}/skills/data-export/scripts/tableau/export_source.py --source-id tableau.example_dashboard \
  --views sheet0,sheet2 \
  --vf "区域=上海区域"
```

生成：

- `data/交叉_example_dashboard.sheet0.csv`
- `data/交叉_example_dashboard.sheet2.csv`
- `export_summary.json`

## 禁止事项

- 禁止调用旧导出脚本
- 禁止显式传 `output_dir`
- 禁止绕过 `$SESSION_ID` 自己拼接导出目录

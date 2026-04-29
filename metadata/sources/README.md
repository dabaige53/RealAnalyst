# Metadata Sources

保存用户提供的原始材料、迁移输入、connector 发现报告和审计证据。

规则：

- 不把这里的文件直接当 dataset。
- 不为了适配 YAML schema 改写原始文件。
- 其他 YAML 的 `source_evidence.source` 应优先引用这里的项目内路径。

# MySQL Sync

这里保存 MySQL connector 发现或同步后的 catalog 快照示例。
这些快照只帮助整理 RealAnalyst metadata，不是业务定义真源。

## 推荐流程

```bash
python3 skills/metadata/adapters/mysql/scripts/discover_catalog.py \
  --source-id <dataset_id> \
  --database <database> \
  --table <table> \
  --connection-ref <ENV_JSON_REF> \
  --output metadata/sync/mysql/<dataset_id>.catalog.json
```

`connection_ref`、`credential_ref`、`dsn_env` 只能写环境变量名或本地 ignored config 引用；不要提交密码、token 或 DSN 明文。

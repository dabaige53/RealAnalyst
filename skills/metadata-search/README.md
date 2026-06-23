# Metadata Search Skill

按需搜索 metadata index，浏览可用数据集目录。

---

## 什么时候用？

- 需要搜指标、字段、术语、数据集或映射定义
- 分析前浏览可用数据集全貌
- 需要轻量 JSON 结果，不想读完整 YAML

---

## 输入与输出

| 类型 | 内容 |
| --- | --- |
| 输入 | 关键词 + 搜索类型（metric / field / term / dataset / mapping / all） |
| 输出 | 机器可读 JSON，含 matches 列表或 catalog 摘要 |
| 下一步 | `RA:metadata context` → `RA:analysis-plan` |

---

## 快速示例

```bash
# 搜指标
python3 skills/metadata-search/scripts/search.py --type metric --query 收入

# 搜全部类型
python3 skills/metadata-search/scripts/search.py --type all --query 订单

# 浏览数据集目录
python3 skills/metadata-search/scripts/catalog.py

# 按业务域过滤
python3 skills/metadata-search/scripts/catalog.py --domain retail
```

---

## 用户会得到什么？

- 按关键词匹配的指标、字段、术语、dataset 或 mapping 摘要。
- 数据集轻量目录（id / domain / grain / top metrics / review 状态）。
- FTS5 全文检索结果（优先），或 JSONL 朴素搜索结果（fallback）。

---

## 常见卡点

| 卡点 | 处理方式 |
| --- | --- |
| `success=false` / index 缺失 | 运行 `python3 skills/metadata/scripts/metadata.py index` |
| 搜索结果为空 | 换更宽泛的关键词，或用 `--type all` |
| 需要维护 YAML | 改用 `RA:metadata` |
| 需要查报告模板/框架 | 改用 `RA:analysis-reference` |

---

## 内部脚本

入口脚本是 `search.py`（搜索）与 `catalog.py`（数据集目录）。配套内部模块：

- `scripts/_bootstrap.py`：定位 workspace 根目录的内部 helper（被 `search.py` / `catalog.py` import，不单独调用）。

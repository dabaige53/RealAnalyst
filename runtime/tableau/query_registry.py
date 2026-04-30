#!/usr/bin/env python3
# ruff: noqa: UP017
# mypy: disable-error-code=import-untyped
from __future__ import annotations

"""Registry 按需查询工具

用法:
    python query_registry.py --source <display_name或source_id或source_key>  # 查询指定数据源完整配置
    python query_registry.py --source <...> --with-context              # 附带指标/维度定义映射上下文
    python query_registry.py --category <category>     # 列出某类别所有数据源
    python query_registry.py --filter <source_id或source_key>     # 查询数据源的筛选器配置
    python query_registry.py --fields <source_id或source_key>     # 查询数据源的字段列表
    python query_registry.py --search <keyword>        # 搜索数据源（名称/描述）
    python query_registry.py --save-group <group_id> --primary-source <source_id> --member-source <source_id>
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

import yaml

from sqlite_store import (
    db_path,
    ensure_store_ready,
    find_groups_by_source,
    list_source_groups,
    load_registry_document,
    load_spec_by_entry_key,
    load_spec_for_entry,
    save_source_group,
)
from source_context import build_source_context

REGISTRY_PATH = db_path()
WORKSPACE_DIR = Path(__file__).resolve().parents[2]
JOBS_DIR = WORKSPACE_DIR / "jobs"
UTC = getattr(datetime, "UTC", datetime.timezone.utc)


def _job_dir(job_id: str) -> Path:
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def _snapshot_path(job_id: str) -> Path:
    return _job_dir(job_id) / "registry_snapshot.json"


def _lock_path(job_id: str) -> Path:
    return _job_dir(job_id) / "source_lock.json"


def _has_id_contract(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("source_id"), str):
            return False
        if entry.get("type") != "domain":
            continue
        views = entry.get("views")
        if not isinstance(views, list):
            return False
        for view in views:
            if not isinstance(view, dict) or not isinstance(view.get("view_id"), str):
                return False
    return True


def load_registry(job_id: str | None = None) -> dict[str, Any]:
    ensure_store_ready()
    if not job_id:
        data = load_registry_document()
        if isinstance(data, dict):
            return data
        raise ValueError("registry.db 格式错误：根节点必须是 dict")

    snapshot_path = _snapshot_path(job_id)
    if snapshot_path.exists():
        with open(snapshot_path, encoding="utf-8") as f:
            snapshot_data = json.load(f)
        if _has_id_contract(snapshot_data):
            return cast(dict[str, Any], snapshot_data)

    data = load_registry_document()
    if not isinstance(data, dict):
        raise ValueError("registry.db 格式错误：根节点必须是 dict")
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def _read_source_lock(job_id: str) -> dict[str, Any] | None:
    lock_path = _lock_path(job_id)
    if not lock_path.exists():
        return None
    with open(lock_path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def _write_source_lock(job_id: str, source_id: str) -> dict[str, Any]:
    payload = {
        "source_id": source_id,
        "locked_at": datetime.datetime.now(UTC).isoformat(),
    }
    lock_path = _lock_path(job_id)
    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _is_active(src: dict[str, Any]) -> bool:
    return str(src.get("status") or "active").lower() == "active"


def _active_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [src for src in data.get("entries", []) if isinstance(src, dict) and _is_active(src)]


def _entry_backend(src: dict[str, Any]) -> str:
    backend = src.get("source_backend")
    if isinstance(backend, str) and backend.strip():
        return backend.strip()
    return "tableau"


def _filter_entries(
    entries: list[dict[str, Any]],
    *,
    backend: str | None = None,
    source_type: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    out = entries
    if backend:
        out = [x for x in out if _entry_backend(x) == backend]
    if source_type:
        out = [x for x in out if str(x.get("type") or "") == source_type]
    if category:
        out = [x for x in out if str(x.get("category") or "") == category]
    return out


def find_source(data: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    for src in _active_entries(data):
        if src.get("source_id") == source_id:
            return src
    return None


def _find_any_source(data: dict[str, Any], query: str) -> dict[str, Any] | None:
    for src in data.get("entries", []):
        if not isinstance(src, dict):
            continue
        for field in ("display_name", "source_id", "key"):
            value = src.get(field)
            if isinstance(value, str) and value == query:
                return src
    return None


def _norm_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.strip().lower(), flags=re.UNICODE)


def resolve_source(data: dict[str, Any], query: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Resolve source by display_name or source_id or key, with fuzzy fallback.

    Deprecated entries are intentionally excluded from normal resolution so they
    cannot be selected accidentally during planning/export flows.
    """
    entries = _active_entries(data)
    query_norm = _norm_text(query)

    # 1) exact display_name (default)
    for src in entries:
        display_name = src.get("display_name")
        if isinstance(display_name, str) and display_name == query:
            return src, []

    # 2) exact source_id
    for src in entries:
        source_id = src.get("source_id")
        if isinstance(source_id, str) and source_id == query:
            return src, []

    # 3) exact key
    for src in entries:
        key = src.get("key")
        if isinstance(key, str) and key == query:
            return src, []

    # 4) normalized contains for suggestions
    candidates: list[dict[str, Any]] = []
    for src in entries:
        display_name = src.get("display_name", "")
        source_id = str(src.get("source_id", ""))
        key = str(src.get("key", ""))
        if query_norm and (
            query_norm in _norm_text(display_name)
            or query_norm in _norm_text(source_id)
            or query_norm in _norm_text(key)
        ):
            candidates.append(src)
    return None, candidates


def _source_alias(src: dict[str, Any]) -> str:
    key = src.get("key")
    return key if isinstance(key, str) else ""


def _load_runtime_spec(src: dict[str, Any]) -> dict[str, Any] | None:
    spec = load_spec_for_entry(src)
    return spec if isinstance(spec, dict) else None


def _derive_fields_from_spec(spec: dict[str, Any]) -> list[str]:
    fields = spec.get("fields")
    if isinstance(fields, list) and all(isinstance(x, str) for x in fields):
        return [x for x in fields if x.strip()]

    derived: list[str] = []
    for section in ("dimensions", "measures"):
        items = spec.get(section)
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict):
                name = it.get("name")
                if isinstance(name, str) and name.strip():
                    derived.append(name.strip())
    # 保持顺序去重
    seen: set[str] = set()
    out: list[str] = []
    for f in derived:
        if f in seen:
            continue
        seen.add(f)
        out.append(f)
    return out


def _get_fields_for_source(src: dict[str, Any]) -> list[str]:
    spec = _load_runtime_spec(src)
    if isinstance(spec, dict):
        derived = _derive_fields_from_spec(spec)
        if derived:
            return derived

    fields = src.get("fields")
    if isinstance(fields, list):
        out = [str(f).strip() for f in fields if str(f).strip()]
        if out:
            return out
    return []


def _recommended_time_field(src: dict[str, Any], fields_list: list[str]) -> str | None:
    semantics = src.get("semantics", {})
    if isinstance(semantics, dict):
        time_fields = semantics.get("time_fields")
        if isinstance(time_fields, list):
            for field in time_fields:
                if isinstance(field, str) and field.strip():
                    return field.strip()
    time_keywords = ["日期", "时间", "date", "time", "month", "year", "day", "week"]
    for field in fields_list:
        lower = field.lower()
        if any(k in lower for k in time_keywords):
            return field
    return None


def _recommended_dimensions(src: dict[str, Any]) -> list[str]:
    semantics = src.get("semantics", {})
    if not isinstance(semantics, dict):
        return []
    dims = semantics.get("primary_dimensions")
    if isinstance(dims, list):
        return [str(x).strip() for x in dims if str(x).strip()][:8]
    return []


def _recommended_measures(src: dict[str, Any]) -> list[str]:
    semantics = src.get("semantics", {})
    if not isinstance(semantics, dict):
        return []
    ms = semantics.get("available_metrics")
    if isinstance(ms, list):
        return [str(x).strip() for x in ms if str(x).strip()][:8]
    return []


def cmd_source(args: argparse.Namespace) -> None:
    """查询指定数据源完整配置"""
    data = load_registry(args.job_id)
    src, candidates = resolve_source(data, args.source)
    if not src:
        deprecated = _find_any_source(data, args.source)
        if deprecated and not _is_active(deprecated):
            print(f"错误: 数据源 '{args.source}' 已停用")
            print(f"停用条目: {deprecated.get('display_name', '')} ({deprecated.get('source_id', '')})")
            sys.exit(1)
        print(f"错误: 未找到数据源 '{args.source}'")
        if candidates:
            print("你可能想找:")
            for cand in candidates[:8]:
                print(
                    f"  - {cand.get('display_name', '')} "
                    f"({cand.get('source_id', '')}, alias: {_source_alias(cand)})"
                )
        else:
            print("可用数据源:", [s.get("source_id") for s in _active_entries(data)])
        sys.exit(1)

    # 输出精简版本（不含 datasource_fields）
    fields_list = _get_fields_for_source(src)

    # 策略检查：时间维度
    time_keywords = [
        "date",
        "time",
        "year",
        "month",
        "day",
        "week",
        "日期",
        "时间",
        "年",
        "月",
        "日",
    ]
    has_time_dim = any(any(k in f.lower() for k in time_keywords) for f in fields_list)

    strategy_hint = []
    if not has_time_dim:
        strategy_hint.append(
            "⚠️ 无明确时间维度列：若需多时间段数据（如 YoY），必须分片下载（Step 1 下载 2024, Step 2 下载 2025），严禁合并查询！"
        )
    else:
        strategy_hint.append("✅ 包含时间维度：支持合并时间段查询（一次下载）。")

    output = {
        "source_id": src.get("source_id"),
        "key": src.get("key"),
        "source_backend": _entry_backend(src),
        "type": src.get("type"),  # dashboard/view/duckdb_table/duckdb_view
        "display_name": src.get("display_name"),
        "description": src.get("description"),
        "category": src.get("category"),
        "dashboard_key": src.get("dashboard_key"),  # view 关联的 dashboard
        "tableau": src.get("tableau", {}),
        "duckdb": src.get("duckdb", {}),
        "views": src.get("views", []),  # dashboard 的子视图列表
        "semantics": src.get("semantics", {}),
        "fields": fields_list,
        "recommended_time_field": _recommended_time_field(src, fields_list),
        "recommended_dimensions": _recommended_dimensions(src),
        "recommended_measures": _recommended_measures(src),
        "strategy_hint": strategy_hint,
        "defaults": src.get("defaults"),  # dashboard 的默认配置
    }
    if args.with_context:
        output["source_context"] = build_source_context(src)

    source_id = src.get("source_id")
    if isinstance(source_id, str) and source_id:
        groups = find_groups_by_source(source_id)
        if groups:
            output["associated_groups"] = [
                {
                    "group_id": g["group_id"],
                    "display_name": g["display_name"],
                    "members": [m.get("source_id") if isinstance(m, dict) else m for m in g["member_sources"]],
                    "use_count": g["use_count"],
                    "last_used_at": g["last_used_at"],
                }
                for g in groups
            ]

    # 移除空值
    output = {k: v for k, v in output.items() if v is not None and v != [] and v != {}}
    print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))


def cmd_category(args: argparse.Namespace) -> None:
    """列出某类别所有数据源"""
    data = load_registry(args.job_id)
    cat_index = data.get("category_index", {})

    if args.category not in cat_index:
        print(f"错误: 未找到类别 '{args.category}'")
        print("可用类别:", list(cat_index.keys()))
        sys.exit(1)

    cat_info = cat_index[args.category]
    print(f"类别: {cat_info.get('display_name', args.category)}")
    print("-" * 40)

    # 适配新结构：从 category_index 的 entries 列表中读取 key
    entries_keys = cat_info.get("entries", cat_info.get("sources", []))

    entries = _filter_entries(
        _active_entries(data),
        backend=args.backend,
        source_type=args.type,
        category=args.category,
    )

    for src in entries:
        if src.get("key") in entries_keys:
            metrics = src.get("semantics", {}).get("available_metrics", [])
            print(f"• {src.get('source_id', '')}")
            print(f"  alias: {src.get('key', '')}")
            print(f"  名称: {src.get('display_name', '')}")
            print(f"  后端: {_entry_backend(src)}")
            print(f"  类型: {src.get('type', '')}")
            print(f"  指标: {', '.join(metrics[:5])}")
            print()


def cmd_filter(args: argparse.Namespace) -> None:
    """查询数据源的筛选器配置"""
    data = load_registry(args.job_id)
    src, candidates = resolve_source(data, args.filter)
    if not src:
        deprecated = _find_any_source(data, args.filter)
        if deprecated and not _is_active(deprecated):
            print(f"错误: 数据源 '{args.filter}' 已停用")
            print(f"停用条目: {deprecated.get('display_name', '')} ({deprecated.get('source_id', '')})")
            sys.exit(1)
        print(f"错误: 未找到数据源 '{args.filter}'")
        if candidates:
            print("你可能想找:")
            for cand in candidates[:8]:
                print(
                    f"  - {cand.get('display_name', '')} "
                    f"({cand.get('source_id', '')}, alias: {_source_alias(cand)})"
                )
        sys.exit(1)

    print(
        f"数据源: {src.get('source_id', '')} "
        f"(alias: {src.get('key', '')}, 名称: {src.get('display_name', '')})"
    )
    print("-" * 40)
    print("可用筛选器:")

    def _label(item: dict[str, Any]) -> str:
        key = item.get("key")
        if isinstance(key, str) and key.strip():
            return key.strip()
        tableau_field = item.get("tableau_field")
        if isinstance(tableau_field, str) and tableau_field.strip():
            return tableau_field.strip()
        return "(unnamed)"

    def _kind(item: dict[str, Any]) -> str:
        kind = item.get("kind")
        if isinstance(kind, str) and kind.strip():
            return kind.strip()
        validation = item.get("validation")
        if isinstance(validation, dict):
            if isinstance(validation.get("pattern"), str) and validation.get("pattern", "").strip():
                return "regex"
            if isinstance(validation.get("allowed_values_file"), str) and validation.get(
                "allowed_values_file", ""
            ).strip():
                return "enum"
            mode = validation.get("mode")
            if isinstance(mode, str) and mode.strip():
                return mode.strip()
        samples = item.get("sample_values")
        if isinstance(samples, list) and samples:
            return "discrete"
        return "unknown"

    filters: list[dict[str, Any]] = []
    parameters: list[dict[str, Any]] = []
    filter_data = _load_runtime_spec(src)
    if isinstance(filter_data, dict):
        raw_filters = filter_data.get("filters", [])
        raw_parameters = filter_data.get("parameters", [])
        if isinstance(raw_filters, list):
            filters = [x for x in raw_filters if isinstance(x, dict)]
        if isinstance(raw_parameters, list):
            parameters = [x for x in raw_parameters if isinstance(x, dict)]

    for f in filters:
        kind = _kind(f)
        samples = f.get("sample_values", [])[:3]
        print(f"  • {_label(f)} ({kind})")
        print(f"    Tableau字段: {f.get('tableau_field', '')}")
        if samples:
            print(f"    示例值: {samples}")
        validation = f.get("validation")
        if isinstance(validation, dict):
            mode = validation.get("mode")
            pattern = validation.get("pattern")
            enum_file = validation.get("allowed_values_file")
            if isinstance(mode, str) and mode.strip():
                print(f"    验证模式: {mode}")
            if isinstance(pattern, str) and pattern.strip():
                print(f"    正则: {pattern}")
            if isinstance(enum_file, str) and enum_file.strip():
                print(f"    枚举文件: {enum_file}")
        description = f.get("description")
        if isinstance(description, str) and description.strip():
            print(f"    说明: {description.strip()}")
        print()

    if parameters:
        print("可用参数:")
        for p in parameters:
            kind = _kind(p)
            print(f"  • {_label(p)} ({kind})")
            print(f"    Tableau字段: {p.get('tableau_field', '')}")
            validation = p.get("validation")
            if isinstance(validation, dict):
                mode = validation.get("mode")
                pattern = validation.get("pattern")
                if isinstance(mode, str) and mode.strip():
                    print(f"    验证模式: {mode}")
                if isinstance(pattern, str) and pattern.strip():
                    print(f"    正则: {pattern}")
            description = p.get("description")
            if isinstance(description, str) and description.strip():
                print(f"    说明: {description.strip()}")
            print()


def cmd_fields(args: argparse.Namespace) -> None:
    """查询数据源的字段列表"""
    data = load_registry(args.job_id)
    src, candidates = resolve_source(data, args.fields)
    if not src:
        deprecated = _find_any_source(data, args.fields)
        if deprecated and not _is_active(deprecated):
            print(f"错误: 数据源 '{args.fields}' 已停用")
            print(f"停用条目: {deprecated.get('display_name', '')} ({deprecated.get('source_id', '')})")
            sys.exit(1)
        print(f"错误: 未找到数据源 '{args.fields}'")
        if candidates:
            print("你可能想找:")
            for cand in candidates[:8]:
                print(
                    f"  - {cand.get('display_name', '')} "
                    f"({cand.get('source_id', '')}, alias: {_source_alias(cand)})"
                )
        sys.exit(1)

    print(f"数据源: {src.get('source_id', '')} (alias: {src.get('key', '')})")
    print("-" * 40)

    fields = _get_fields_for_source(src)
    print(f"输出字段 ({len(fields)}):")
    for f in fields:
        print(f"  • {f}")


def cmd_search(args: argparse.Namespace) -> None:
    """搜索数据源"""
    data = load_registry(args.job_id)
    if args.job_id:
        lock_info = _read_source_lock(args.job_id)
        if lock_info and isinstance(lock_info.get("source_id"), str):
            source_id = lock_info["source_id"]
            src = find_source(data, source_id)
            if not src:
                print(f"错误: 锁定的数据源不存在 '{source_id}'")
                sys.exit(1)
            output = {
                "source_locked": True,
                "source_id": source_id,
                "key": src.get("key"),
                "locked_at": lock_info.get("locked_at"),
                "display_name": src.get("display_name"),
                "description": src.get("description"),
                "category": src.get("category"),
            }
            output = {k: v for k, v in output.items() if v is not None}
            print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))
            return
    keyword = args.search.lower()
    keyword_norm = _norm_text(args.search)

    entries = _filter_entries(
        _active_entries(data),
        backend=args.backend,
        source_type=args.type,
        category=args.category,
    )
    if args.category_like:
        entries = [
            x for x in entries if args.category_like.lower() in str(x.get("category") or "").lower()
        ]

    results = []
    for src in entries:
        name = src.get("display_name", "").lower()
        desc = src.get("description", "").lower()
        suitable = " ".join(src.get("semantics", {}).get("suitable_for", [])).lower()
        metrics = " ".join(src.get("semantics", {}).get("available_metrics", [])).lower()
        dims = " ".join(src.get("semantics", {}).get("primary_dimensions", [])).lower()

        source_id = str(src.get("source_id", "")).lower()
        key = str(src.get("key", "")).lower()
        haystack_norm = " ".join([
            _norm_text(str(src.get("display_name", ""))),
            _norm_text(str(src.get("description", ""))),
            _norm_text(" ".join(src.get("semantics", {}).get("suitable_for", []) or [])),
            _norm_text(" ".join(src.get("semantics", {}).get("available_metrics", []) or [])),
            _norm_text(" ".join(src.get("semantics", {}).get("primary_dimensions", []) or [])),
            _norm_text(str(src.get("source_id", ""))),
            _norm_text(str(src.get("key", ""))),
        ])

        if (
            keyword in name or keyword in desc or keyword in suitable or keyword in metrics or keyword in dims
            or keyword in source_id or keyword in key
            or (keyword_norm and keyword_norm in haystack_norm)
        ):
            results.append(src)

    if not results:
        print(f"未找到匹配 '{args.search}' 的数据源")
        sys.exit(0)

    print(f"找到 {len(results)} 个匹配的数据源:")
    print("-" * 40)
    for src in results:
        semantics = src.get("semantics", {})
        print(f"• {src.get('source_id', '')}")
        print(f"  alias: {src.get('key', '')}")
        print(f"  名称: {src.get('display_name', '')}")
        print(f"  后端: {_entry_backend(src)}")
        print(f"  类型: {src.get('type', '')}")
        print(f"  类别: {src.get('category', '')}")
        print(f"  适用: {semantics.get('suitable_for', [])}")
        recommended_time = _recommended_time_field(src, _get_fields_for_source(src))
        if recommended_time:
            print(f"  推荐时间字段: {recommended_time}")
        recommended_dims = _recommended_dimensions(src)
        if recommended_dims:
            print(f"  推荐维度: {recommended_dims[:3]}")
        recommended_measures = _recommended_measures(src)
        if recommended_measures:
            print(f"  推荐指标: {recommended_measures[:3]}")
        tableau = src.get('tableau', {}) or {}
        duckdb = src.get('duckdb', {}) or {}
        if tableau.get('view_luid'):
            print(f"  view_luid: {tableau.get('view_luid', '')}")
        if duckdb.get('object_name'):
            print(f"  duckdb对象: {duckdb.get('object_name', '')}")
        print()

    if args.job_id and results:
        source_id = results[0].get("source_id")
        if isinstance(source_id, str) and source_id:
            locked = _write_source_lock(args.job_id, source_id)
            print(f"已锁定数据源: {locked['source_id']}")


def cmd_groups(args: argparse.Namespace) -> None:
    """列出数据源组（可指定 source_id 过滤）"""
    if args.groups == "__all__":
        groups = list_source_groups()
    else:
        groups = find_groups_by_source(args.groups)

    if not groups:
        print("未找到数据源组" + (f"（过滤: {args.groups}）" if args.groups != "__all__" else ""))
        return

    print(f"找到 {len(groups)} 个数据源组:")
    print("-" * 40)
    for g in groups:
        members = g.get("member_sources", [])
        member_ids = [m.get("source_id") if isinstance(m, dict) else str(m) for m in members]
        print(f"• [{g['group_id']}] {g.get('display_name', '')}")
        print(f"  主数据源: {g['primary_source_id']}")
        print(f"  成员: {member_ids}")
        print(f"  使用次数: {g.get('use_count', 0)}  最后使用: {g.get('last_used_at', 'N/A')}")
        if g.get("notes"):
            print(f"  备注: {g['notes']}")
        print()


def cmd_save_group(args: argparse.Namespace) -> None:
    """保存已确认的数据源组。"""
    data = load_registry(args.job_id)
    primary, _ = resolve_source(data, args.primary_source)
    if not primary:
        print(f"错误: 未找到 primary source '{args.primary_source}'")
        sys.exit(1)

    member_inputs = list(args.member_source or [])
    if args.primary_source not in member_inputs:
        member_inputs.insert(0, args.primary_source)

    members: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_key in member_inputs:
        src, _ = resolve_source(data, source_key)
        if not src:
            print(f"错误: 未找到 member source '{source_key}'")
            sys.exit(1)
        source_id = str(src.get("source_id") or "")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        members.append(
            {
                "source_id": source_id,
                "display_name": str(src.get("display_name") or ""),
                "role": "primary" if source_id == primary.get("source_id") else "supplementary",
            }
        )

    now = datetime.datetime.now(UTC).isoformat()
    group_doc = {
        "group_id": args.save_group,
        "display_name": args.group_display_name or args.save_group,
        "primary_source_id": primary.get("source_id"),
        "member_sources": members,
        "created_at": now,
        "last_used_at": now,
        "use_count": 1,
        "notes": args.group_notes,
    }
    save_source_group(group_doc)
    print(yaml.dump({"success": True, "source_group": group_doc}, allow_unicode=True, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Registry 按需查询工具")
    parser.add_argument("--job-id", help="job 级缓存与锁定所需的 job id")
    parser.add_argument("--backend", choices=["tableau", "duckdb"], help="按数据源后端过滤")
    parser.add_argument("--type", help="按 source type 过滤，如 view/domain/duckdb_view/duckdb_table")
    parser.add_argument("--category-like", dest="category_like", help="按类别模糊过滤（仅 search 生效）")
    parser.add_argument("--with-context", action="store_true", help="附带指标/维度定义映射上下文")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", "-s", help="查询指定数据源完整配置")
    group.add_argument("--category", "-c", help="列出某类别所有数据源")
    group.add_argument("--filter", "-f", help="查询数据源的筛选器配置")
    group.add_argument("--fields", help="查询数据源的字段列表")
    group.add_argument("--search", help="搜索数据源（名称/描述/适用场景）")
    group.add_argument("--groups", nargs="?", const="__all__", help="列出数据源组（可指定 source_id 过滤）")
    group.add_argument("--save-group", help="保存数据源组 group_id")
    parser.add_argument("--primary-source", help="保存 source group 时的主数据源")
    parser.add_argument("--member-source", action="append", default=[], help="保存 source group 时的成员数据源，可重复")
    parser.add_argument("--group-display-name", help="保存 source group 时的展示名")
    parser.add_argument("--group-notes", help="保存 source group 时的备注")

    args = parser.parse_args()

    if args.source:
        cmd_source(args)
    elif args.category:
        cmd_category(args)
    elif args.filter:
        cmd_filter(args)
    elif args.fields:
        cmd_fields(args)
    elif args.search:
        cmd_search(args)
    elif args.groups is not None:
        cmd_groups(args)
    elif args.save_group:
        if not args.primary_source:
            parser.error("--save-group requires --primary-source")
        cmd_save_group(args)


if __name__ == "__main__":
    main()

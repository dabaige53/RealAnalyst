#!/usr/bin/env python3
from __future__ import annotations

"""
Tableau View Export Script

Export Tableau view data to CSV with auto-generated manifest.json.

Usage:
    python3 export.py <view_url> <output_dir> [dataset_id]

Example:
    python3 export.py "https://tableau.example.com/#/views/Sales/Dashboard" outputs/job_001
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from auth import TableauAuth, get_auth

from runtime.tableau.sqlite_store import (
    ensure_store_ready,
    get_entry_by_key,
    get_entry_by_view_luid,
    load_allowed_values,
    load_registry_document,
    load_spec_by_entry_key,
    load_spec_by_ref,
    normalize_allowed_value,
)

_DATE_RE = re.compile(r"^(?P<y>\d{4})[-/](?P<m>\d{1,2})[-/](?P<d>\d{1,2})$")


def _workspace_dir() -> Path:
    return WORKSPACE_DIR


def _export_budget_path(job_id: str) -> Path:
    jobs_dir = _workspace_dir() / "jobs" / job_id
    return jobs_dir / "export_budget.json"


def _init_export_budget() -> dict[str, Any]:
    return {"max_count": 5, "used_count": 0, "history": []}


def _load_export_budget(path: Path) -> dict[str, Any]:
    if not path.exists():
        budget = _init_export_budget()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(budget, ensure_ascii=False, indent=2), encoding="utf-8")
        return budget

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}

    max_count = data.get("max_count", 5)
    used_count = data.get("used_count", 0)
    history = data.get("history", [])

    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 2

    try:
        used_count = int(used_count)
    except (TypeError, ValueError):
        used_count = 0

    if not isinstance(history, list):
        history = []

    normalized = {"max_count": max_count, "used_count": used_count, "history": history}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def _record_export_budget(
    path: Path,
    budget: dict[str, Any],
    *,
    success: bool,
    view_luid: str | None,
    domain_key: str | None,
) -> None:
    used_count = budget.get("used_count", 0)
    try:
        used_count = int(used_count)
    except (TypeError, ValueError):
        used_count = 0

    history = budget.get("history", [])
    if not isinstance(history, list):
        history = []

    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "view_luid": view_luid,
            "domain_key": domain_key,
            "success": success,
        }
    )

    max_count = budget.get("max_count", 2)
    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 2

    new_used_count = used_count + 1 if success else used_count
    updated = {"max_count": max_count, "used_count": new_used_count, "history": history}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_scalar(value: str) -> str:
    v = value.strip()
    if v.lower() in {"true", "false"}:
        return v.lower()

    m = _DATE_RE.match(v)
    if m:
        y = int(m.group("y"))
        mo = int(m.group("m"))
        d = int(m.group("d"))
        return f"{y:04d}-{mo:02d}-{d:02d}"

    return v


def _parse_kv_list(
    items: list[str] | None, *, source: str
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Parse KEY=VALUE list with dedup; fail on conflicts."""
    kv: dict[str, str] = {}
    resolved: list[dict[str, str]] = []
    if not items:
        return kv, resolved

    for raw in items:
        if "=" not in raw:
            raise ValueError(f"{source} 参数格式错误，必须是 KEY=VALUE：{raw}")
        key_raw, value_raw = raw.split("=", 1)
        key = key_raw.strip()
        if not key:
            raise ValueError(f"{source} 参数 key 不能为空：{raw}")
        value = _normalize_scalar(value_raw)

        if key in kv and kv[key] != value:
            raise ValueError(f"参数冲突：{key} 同时出现多个不同值（{kv[key]} vs {value}）")

        kv[key] = value
        resolved.append(
            {
                "key": key,
                "raw_input": raw,
                "normalized_value": value,
                "source": source,
            }
        )

    return kv, resolved


def _normalize_vf_vp_kv(
    *,
    vf_kv: dict[str, str],
    vp_kv: dict[str, str],
) -> tuple[dict[str, str], dict[str, str], dict[str, str], list[str]]:
    """Normalize keys across vf/vp.

    Rules:
    - Accept accidental key prefixes: `vf_foo=1`, `vp_bar=2`.
    - `vf_` implies view filter (vf), `vp_` implies view parameter (vp).
    - Keys are normalized by stripping the prefix.
    - If a key is passed under the wrong flag but contains an explicit prefix,
      we route it to the implied bucket.

    Returns:
      (vf_norm, vp_norm, key_map, warnings)
    """

    def strip_prefix(key: str) -> tuple[str, str | None]:
        if key.startswith("vf_"):
            return key[3:], "vf"
        if key.startswith("vp_"):
            return key[3:], "vp"
        return key, None

    vf_norm: dict[str, str] = {}
    vp_norm: dict[str, str] = {}
    key_map: dict[str, str] = {}
    warnings: list[str] = []

    def add(target: dict[str, str], key: str, value: str) -> None:
        if key in target and target[key] != value:
            raise ValueError(f"参数冲突：{key} 同时出现多个不同值（{target[key]} vs {value}）")
        target[key] = value

    for raw_key, value in vf_kv.items():
        key, implied = strip_prefix(raw_key)
        key_map[raw_key] = key
        if implied == "vp":
            warnings.append(f"检测到 vp_ 前缀参数出现在 --vf：{raw_key}，已按参数处理")
            add(vp_norm, key, value)
        else:
            add(vf_norm, key, value)

    for raw_key, value in vp_kv.items():
        key, implied = strip_prefix(raw_key)
        key_map[raw_key] = key
        if implied == "vf":
            warnings.append(f"检测到 vf_ 前缀筛选出现在 --vp：{raw_key}，已按筛选处理")
            add(vf_norm, key, value)
        else:
            add(vp_norm, key, value)

    # Cross-bucket conflict check after normalization
    for k in set(vf_norm.keys()) & set(vp_norm.keys()):
        if vf_norm[k] != vp_norm[k]:
            raise ValueError(f"禁止混用：同一 key 同时出现在 vf/vp 且值不同：{k}")
        # Same value, keep vf and drop vp to avoid ambiguity
        vp_norm.pop(k, None)
        warnings.append(f"检测到同一 key 同时出现在 vf/vp：{k}，已保留 vf")

    return vf_norm, vp_norm, key_map, warnings


def _registry_path() -> Path:
    ensure_store_ready()
    return WORKSPACE_DIR / "runtime" / "tableau" / "registry.db"


def _load_registry() -> dict[str, Any]:
    ensure_store_ready()
    data = load_registry_document()
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError("registry.db 格式错误：缺少 entries")
    return data


def _get_max_concurrent() -> int:
    try:
        registry = _load_registry()
        return registry.get("defaults", {}).get("export_options", {}).get("max_concurrent", 3)
    except Exception:
        return 3


def _get_entry_for_view_luid(view_luid: str) -> dict[str, Any] | None:
    return get_entry_by_view_luid(view_luid)


def _resolve_spec_for_entry(entry: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    key = entry.get("key")
    if isinstance(key, str) and key.strip():
        spec = load_spec_by_entry_key(key)
        if isinstance(spec, dict):
            return key.strip(), spec

    raise FileNotFoundError(
        f"runtime spec not found in registry.db for entry: {entry.get('key') or entry.get('source_id') or 'unknown'}"
    )


def _load_runtime_spec(spec_key: str) -> dict[str, Any]:
    spec = load_spec_by_entry_key(spec_key)
    if not isinstance(spec, dict):
        raise FileNotFoundError(f"runtime spec not found in registry.db: {spec_key}")
    return spec


def _validate_against_runtime_spec(
    *,
    spec_key: str,
    vf_kv: dict[str, str],
    vp_kv: dict[str, str] | None = None,
) -> list[str]:
    spec = _load_runtime_spec(spec_key)
    filters = spec.get("filters") or []
    parameters = spec.get("parameters") or []
    if not isinstance(filters, list) or not isinstance(parameters, list):
        raise ValueError(f"runtime spec 格式错误：{spec_key}")

    allowed: dict[str, dict[str, Any]] = {}
    for f in filters + parameters:
        if isinstance(f, dict):
            field = f.get("tableau_field") or f.get("key")
            if field:
                allowed[str(field)] = f

    all_kv = vf_kv.copy()
    if vp_kv:
        all_kv.update(vp_kv)

    for key in list(all_kv.keys()):
        if key not in allowed:
            raise ValueError(f"未知筛选字段（未在 runtime spec 定义）：{key}")

    for key in set(all_kv.keys()):
        if key.endswith("_开始"):
            end_key = key[:-3] + "_结束"
            if end_key not in all_kv:
                raise ValueError(f"缺少配对参数：{end_key}")
        if key.endswith("_结束"):
            start_key = key[:-3] + "_开始"
            if start_key not in all_kv:
                raise ValueError(f"缺少配对参数：{start_key}")

    warnings: list[str] = []

    def _load_allowed_values(f: dict[str, Any]) -> list[str] | None:
        # 优先级: allowed_values_file > allowed_values > sample_values
        file_ref = None
        validation = f.get("validation")
        if isinstance(validation, dict):
            file_ref = validation.get("allowed_values_file")
        if isinstance(file_ref, str) and file_ref.strip():
            allowed_values = load_allowed_values(file_ref)
            if allowed_values is None:
                raise ValueError(f"allowed_values_file 未找到或格式错误：{file_ref}")
            return allowed_values

        allowed_values = f.get("allowed_values")
        if isinstance(allowed_values, list) and allowed_values:
            return [str(x) for x in allowed_values]

        # 降级：使用 sample_values 作为校验依据
        sample_values = f.get("sample_values")
        if isinstance(sample_values, list) and sample_values:
            return [str(x) for x in sample_values]

        return None

    def _check_value(field: str, value: str) -> str:
        f = allowed[field]
        validation = f.get("validation")
        if not isinstance(validation, dict):
            return value

        mode = str(validation.get("mode", "")).strip().lower()
        if mode != "strict":
            return value

        # 正则校验
        pattern = validation.get("pattern")
        if isinstance(pattern, str) and pattern:
            import re as regex_module

            vals = [v.strip() for v in value.split(",") if v.strip()]
            for v in vals:
                if not regex_module.match(pattern, v):
                    raise ValueError(f"正则校验失败：{field}={v}（期望匹配 {pattern}）")
            return value

        # 枚举校验（默认多选）
        allowed_values = _load_allowed_values(f)
        if not allowed_values:
            raise ValueError(
                f"严格枚举校验缺少枚举值配置（allowed_values_file 或 sample_values）：{field}"
            )
        file_ref = validation.get("allowed_values_file") if isinstance(validation, dict) else None
        vals = [v.strip() for v in value.split(",") if v.strip()]
        normalized_vals: list[str] = []
        for v in vals:
            normalized = normalize_allowed_value(str(file_ref), v) if isinstance(file_ref, str) and file_ref.strip() else v
            if normalized != v:
                warnings.append(f"枚举别名已归一：{field}={v} -> {normalized}")
            if normalized not in allowed_values:
                raise ValueError(
                    f"枚举值非法：{field}={v}（允许值：{allowed_values[:5]}{'...' if len(allowed_values) > 5 else ''}）"
                )
            normalized_vals.append(normalized)
        return ",".join(normalized_vals)

    for k, v in list(all_kv.items()):
        all_kv[k] = _check_value(k, v)

    for k in list(vf_kv.keys()):
        if k in all_kv:
            vf_kv[k] = all_kv[k]
    if vp_kv:
        for k in list(vp_kv.keys()):
            if k in all_kv:
                vp_kv[k] = all_kv[k]

    return warnings


def _perform_assertions(
    csv_path: Path,
    spec_key: str,
    resolved_params: list[dict[str, str]],
    view_id: str,
    view_name: str,
) -> tuple[bool, dict[str, Any]]:
    spec = _load_runtime_spec(spec_key)
    filters_spec = {
        str(f["key"]): f for f in spec.get("filters", []) if isinstance(f, dict) and f.get("key")
    }

    special_values = spec.get("special_values") if isinstance(spec, dict) else None
    ignore_observed_values: dict[str, list[str]] = {}
    if isinstance(special_values, dict):
        iov = special_values.get("ignore_observed_values")
        if isinstance(iov, dict):
            for k, v in iov.items():
                if isinstance(k, str) and isinstance(v, list):
                    ignore_observed_values[k] = [str(x) for x in v]

    applied_filters = {p["key"]: p["normalized_value"] for p in resolved_params}
    checks = []
    failed_checks = []

    observed_data: dict[str, set[str]] = {}
    header = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            for row in reader:
                for col in header:
                    val = (row[col] or "").strip()
                    if col not in observed_data:
                        observed_data[col] = set()
                    observed_data[col].add(val)
    except Exception as e:
        return False, {"error": f"Failed to read CSV for assertion: {e}"}

    processed_keys = set()
    for key, spec_item in filters_spec.items():
        if key not in applied_filters or key in processed_keys:
            continue

        req_val = applied_filters[key]
        tableau_field = spec_item.get("tableau_field", key)
        check_type = spec_item.get("type") or spec_item.get("kind")

        if check_type in ("enum", "string_exact"):
            processed_keys.add(key)
            if tableau_field in header:
                actual_values = observed_data[tableau_field]
                if check_type == "enum":
                    multi = bool(spec_item.get("multi_select"))
                    allowed = (
                        {v.strip() for v in req_val.split(",") if v.strip()} if multi else {req_val}
                    )
                else:
                    allowed = {req_val}

                illegal = {v for v in actual_values if v and v not in allowed}
                # 允许 spec 声明“观测值忽略项”（例如视图包含汇总行：'全部'）
                ignore_vals = {"全部"}
                ignore_vals |= set(ignore_observed_values.get(key, []))
                ignore_vals |= set(ignore_observed_values.get(tableau_field, []))
                illegal = {v for v in illegal if v not in ignore_vals}
                if illegal:
                    msg = (
                        f"列 '{tableau_field}' 包含非预期值: {sorted(illegal)}。"
                        f"预期为 {sorted(allowed)} 的子集"
                    )
                    checks.append(
                        {
                            "key": key,
                            "status": "fail",
                            "observed_summary": f"观测值: {sorted(actual_values)}",
                            "error": msg,
                        }
                    )
                    failed_checks.append(msg)
                else:
                    checks.append(
                        {
                            "key": key,
                            "status": "pass",
                            "observed_summary": f"观测值: {sorted(actual_values)}",
                        }
                    )

        # 说明：平台 API 侧仅支持绝对/枚举匹配。
        # *_开始/*_结束 这类“区间”在业务上是 Tableau 参数驱动的过滤逻辑，
        # 本端无法通过 CSV 观测值可靠验证区间是否生效，因此不做断言。

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "view_luid": view_id,
        "view_name": view_name,
        "csv_path": str(csv_path),
        "resolved_params": resolved_params,
        "checks": checks,
        "failed_checks": failed_checks,
    }
    return len(failed_checks) == 0, report


def _request_with_retry(
    url: str,
    headers: dict,
    view_id: str,
    timeout: int = 120,
    session: requests.Session | None = None,
) -> requests.Response:
    """Helper request wrapper with exponential backoff and jitter."""
    max_attempts = 5
    last_resp: requests.Response | None = None
    for attempt in range(1, max_attempts + 1):
        start_time = time.time()
        try:
            client = session or requests
            resp = client.get(url, headers=headers, timeout=timeout)
            status_code = resp.status_code
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(
                f"[Tableau] View export attempt: view_luid={view_id}, "
                f"attempt={attempt}, status_code={status_code}, elapsed_ms={elapsed_ms}"
            )

            if status_code == 200:
                return resp

            last_resp = resp
            # Retry on 429 and 5xx
            if status_code == 429 or 500 <= status_code < 600:
                pass  # Continue to retry
            else:
                return resp  # Other status codes (401, 404, etc.) fail fast

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.SSLError,
        ) as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(
                f"[Tableau] View export attempt failed: view_luid={view_id}, "
                f"attempt={attempt}, error={type(e).__name__}, elapsed_ms={elapsed_ms}"
            )
            if attempt == max_attempts:
                raise

        if attempt < max_attempts:
            # backoff: base=0.5s * (2 ** (attempt-1)) + jitter(0..0.5s), cap sleep at 10s
            sleep_time = 0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            sleep_time = min(sleep_time, 10.0)
            time.sleep(sleep_time)

    if last_resp is None:
        raise RuntimeError(f"导出失败：{max_attempts} 次重试均未获得响应 view_luid={view_id}")
    return last_resp


def parse_view_url(url: str) -> tuple[str, str] | None:
    """Extract workbook and view names from Tableau URL.

    Returns:
        (workbook_name, view_url_name) if URL format is valid
        None if not a valid URL format (may be a view name)
    """
    if "views/" not in url:
        return None  # 可能是视图名，返回 None 让调用方处理

    parts = url.split("views/")[1].split("?")[0].split("/")
    if len(parts) < 2:
        return None

    return parts[0], parts[1]


def get_all_views(auth: TableauAuth) -> list[dict]:
    """获取所有视图列表。"""
    views_url = f"{auth.api_base}/views"
    resp = auth.session.get(views_url, headers=auth.get_headers(), timeout=60)
    resp.raise_for_status()
    return resp.json().get("views", {}).get("view", [])


def find_view_id(auth: TableauAuth, view_url_name: str) -> tuple[str, str]:
    """Find view ID by URL name."""
    views = get_all_views(auth)
    for v in views:
        if v.get("viewUrlName") == view_url_name:
            return v["id"], v.get("name", view_url_name)

    available = [v.get("viewUrlName") for v in views[:20]]
    raise ValueError(f"未找到视图 '{view_url_name}'。可用视图: {available}")


def find_view_by_name(auth: TableauAuth, view_name: str) -> tuple[str, str]:
    """按视图名称查找（支持精确匹配和模糊匹配）。

    Args:
        auth: Tableau 认证对象
        view_name: 视图名称（支持中文）

    Returns:
        (view_id, view_name) 元组

    Raises:
        ValueError: 未找到匹配的视图
    """
    views = get_all_views(auth)

    # 1. 精确匹配
    for v in views:
        if v.get("name") == view_name:
            return v["id"], v["name"]

    # 2. 模糊匹配（视图名包含搜索词）
    matches = []
    for v in views:
        name = v.get("name", "")
        if view_name in name:
            matches.append(v)

    if len(matches) == 1:
        return matches[0]["id"], matches[0]["name"]
    elif len(matches) > 1:
        match_names = [m.get("name") for m in matches[:10]]
        raise ValueError(
            f"找到 {len(matches)} 个匹配视图，请指定更精确的名称或使用 --view-luid:\n"
            f"  匹配列表: {match_names}"
        )

    # 3. 未找到，给出建议
    raise ValueError(
        f"未找到视图 '{view_name}'。\n"
        f"建议:\n"
        f"  1. 使用 list.py 查看所有视图\n"
        f"  2. 使用 --view-luid <LUID> 直接指定视图 ID\n"
        f"  3. 确认视图名称拼写正确"
    )


def infer_column_type(values: list[str]) -> str:
    """Infer column data type from sample values."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "string"

    sample = non_empty[:100]

    try:
        for v in sample:
            int(v.replace(",", ""))
        return "integer"
    except ValueError:
        pass

    try:
        for v in sample:
            float(v.replace(",", "").replace("%", ""))
        return "float"
    except ValueError:
        pass

    date_patterns = ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m"]
    for pattern in date_patterns:
        try:
            for v in sample[:10]:
                datetime.strptime(v, pattern)
            return "date"
        except ValueError:
            continue

    return "string"


def infer_semantic_type(col_name: str, col_type: str, values: list[str]) -> str | None:
    """Infer semantic type based on column name and values."""
    name_lower = col_name.lower()

    if "产品线" in col_name or "route" in name_lower:
        return "route"
    if "城市" in col_name or "city" in name_lower:
        return "city"
    if "机场" in col_name or "airport" in name_lower:
        return "airport_code"

    if "率" in col_name or "rate" in name_lower or any("%" in str(v) for v in values[:10]):
        return "percentage"
    if "营收" in col_name or "revenue" in name_lower or "金额" in col_name:
        return "currency"
    if "量" in col_name or "数" in col_name or "count" in name_lower:
        return "count"

    if col_type == "date" and ("月" in col_name or "month" in name_lower):
        return "date_month"

    return None


def pivot_long_to_wide(csv_content: str) -> tuple[str | None, str | None, str | None]:
    """将长格式数据 pivot 成宽格式,并尝试生成具备业务含义的建议文件名。

    Returns:
        (pivot_content, warning, suggested_filename)
    """
    lines = csv_content.strip().split("\n")
    if len(lines) < 2:
        return None, "数据行数不足", None

    reader = csv.reader(lines)
    header = next(reader)
    rows = list(reader)

    if "度量名称" not in header or "度量值" not in header:
        return None, "未检测到 '度量名称' 和 '度量值' 列,跳过 pivot", None

    measure_name_idx = header.index("度量名称")
    measure_value_idx = header.index("度量值")
    dim_indices = [i for i in range(len(header)) if i not in (measure_name_idx, measure_value_idx)]
    dim_names = [header[i] for i in dim_indices]

    measure_names: set[str] = set()
    for row in rows:
        if len(row) > measure_name_idx:
            measure_names.add(row[measure_name_idx])

    if len(measure_names) > 50:
        return None, f"度量名称基数过高 ({len(measure_names)}),跳过 pivot", None

    pivot_data: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        if len(row) <= max(measure_name_idx, measure_value_idx):
            continue
        dim_key = tuple(row[i] if i < len(row) else "" for i in dim_indices)
        measure_name = row[measure_name_idx]
        measure_value = row[measure_value_idx]

        if dim_key not in pivot_data:
            pivot_data[dim_key] = {}
        pivot_data[dim_key][measure_name] = measure_value

    sorted_measures = sorted(measure_names)
    pivot_header = dim_names + sorted_measures

    # 智能建议文件名：交叉_{行维度}_{度量概括}
    suggested_filename = None
    if dim_names:
        main_dim = dim_names[-1]  # 取最后一个维度通常是细分维度
        measure_summary = "多项指标" if len(sorted_measures) > 2 else "×".join(sorted_measures)
        suggested_filename = f"交叉分析_{main_dim}_{measure_summary}.csv"

    output_lines = [",".join(pivot_header)]
    for dim_key, measures in pivot_data.items():
        row_values = list(dim_key) + [measures.get(m, "") for m in sorted_measures]
        escaped = [f'"{v}"' if "," in v else v for v in row_values]
        output_lines.append(",".join(escaped))

    return "\n".join(output_lines), None, suggested_filename


def build_manifest(
    csv_content: str,
    view_url: str,
    view_id: str,
    dataset_id: str,
    source_key: str = "",
    display_name: str = "",
    api_url: str = "",
    filters: dict[str, str] | None = None,
    tableau_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build manifest.json from CSV content.

    Args:
        csv_content: CSV 文件内容
        view_url: 原始视图 URL
        view_id: 视图 LUID
        dataset_id: 数据集 ID
        source_key: 数据源标识键 (如 sales.ai_)
        display_name: 数据源显示名称
        api_url: 完整的 API 调用 URL (不含认证信息)
        filters: 应用的筛选器 {"字段名": "值"}
        tableau_metadata: Tableau 元信息
    """
    lines = csv_content.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("CSV 数据为空")

    reader = csv.reader(lines)
    header = next(reader)
    rows = list(reader)

    column_values: dict[str, list[str]] = {col: [] for col in header}
    for row in rows:
        for i, col in enumerate(header):
            if i < len(row):
                column_values[col].append(row[i])

    columns_schema = []
    for col in header:
        values = column_values[col]
        col_type = infer_column_type(values)
        semantic = infer_semantic_type(col, col_type, values)

        col_def: dict[str, str] = {"name": col, "type": col_type}
        if semantic:
            col_def["semantic_type"] = semantic
        columns_schema.append(col_def)

    metadata = dict(tableau_metadata or {})
    source_ref = metadata.get("page_url") or view_url

    return {
        "id": dataset_id,
        "source_key": source_key or "",
        "display_name": display_name or "",
        "view_luid": view_id,
        "api_url": api_url or "",
        "filters": filters or {},
        "source_type": "tableau",
        "source_ref": source_ref,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "schema": {"columns": columns_schema},
        "tableau": metadata,
        "lineage": {
            "source": f"tableau:{view_id}",
            "transforms": [],
        },
    }


def _build_tableau_page_url(base_url: str, site_content_url: str, content_url: str) -> str:
    base = base_url.rstrip("/")
    content = content_url.strip().lstrip("/")
    if not base or not content:
        return ""
    if "/sheets/" in content:
        workbook, view = content.split("/sheets/", 1)
        if workbook and view:
            content = f"{workbook}/{view}"
    site = site_content_url.strip().strip("/")
    if site:
        return f"{base}/#/site/{site}/views/{content}"
    return f"{base}/#/views/{content}"


def get_domain_config(domain_key: str) -> dict[str, Any]:
    """Read domain configuration from SQLite registry store.

    Args:
        domain_key: Domain key (e.g., "example_dashboard" or legacy "domain.example_dashboard")

    Returns:
        Domain runtime dict with views[] array

    Raises:
        SystemExit: If domain not found or views[] missing/empty
    """

    ensure_store_ready()

    key = domain_key
    if key.startswith("domain.") and "." in key:
        key = key.split(".", 1)[1]

    entry = get_entry_by_key(key)
    if not entry:
        print(
            json.dumps(
                {"success": False, "error": f"Domain '{domain_key}' not found in registry.db"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if entry.get("type") != "domain":
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Entry '{key}' is not a domain (type={entry.get('type')})",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    views = entry.get("views", [])
    if not views:
        print(
            json.dumps(
                {"success": False, "error": f"Domain '{key}' has no views[] configured"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    return entry


def export_view(
    view_url: str,
    output_dir: str,
    dataset_id: str | None = None,
    view_luid: str | None = None,
    vf_filters: list[str] | None = None,
    vp_filters: list[str] | None = None,
    output_name: str | None = None,
    auth: TableauAuth | None = None,
    time_field: str | None = None,
    time_window: str | None = None,
    source_key: str | None = None,
    source_display_name: str | None = None,
    tableau_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Export Tableau view to CSV with manifest.

    Args:
        view_url: Tableau view URL or view name
        output_dir: Output directory path
        dataset_id: Optional dataset ID (auto-generated if not provided)
        view_luid: Optional view LUID to skip lookup
        vf_filters: Optional list of filters in "field=value" format
        output_name: Output file base name (e.g. "raw_sales_ai_2025q4_sh")
        auth: Optional existing auth session
    """
    own_auth = False
    if auth is None:
        auth = get_auth()
        own_auth = True
        try:
            auth.signin()
        except Exception as e:
            return {"success": False, "error": str(e)}

    try:
        if view_luid:
            view_id = view_luid
            view_name = "SpecifiedView"
            print(f"[Tableau] 使用指定 LUID: {view_id}")
        else:
            url_result = parse_view_url(view_url)
            if url_result:
                _, view_url_name = url_result
                print(f"[Tableau] 从 URL 解析视图: {view_url_name}")
                view_id, view_name = find_view_id(auth, view_url_name)
            else:
                print(f"[Tableau] 按名称查找视图: {view_url}")
                view_id, view_name = find_view_by_name(auth, view_url)
    except (ValueError, FileNotFoundError) as e:
        if own_auth:
            auth.signout()
        return {
            "success": False,
            "error": str(e),
            "hint": "请使用 --view-luid 直接指定视图 LUID，或使用 list.py 查看可用视图",
        }

    try:
        print(f"[Tableau] 导出视图: {view_name} (ID: {view_id})")

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        # 数据文件输出到 data/ 子目录
        data_dir = Path(output_dir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        raw_filename = f"{output_name}.csv" if output_name else "data.csv"
        csv_path = data_dir / raw_filename

        from urllib.parse import urlencode

        # Query Contract (REST-only):
        # - Do not inherit querystring from view_url (avoid non-deterministic duplicates)
        # - vf is used for filtering
        # - vf are passed as vf_<key>=<value> for REST /data (tbi validated)
        resolved_params: list[dict[str, str]] = []
        try:
            vf_kv_raw, vf_rows = _parse_kv_list(vf_filters, source="vf")
            vp_kv_raw, vp_rows = _parse_kv_list(vp_filters, source="vp")
            resolved_params.extend(vf_rows)
            resolved_params.extend(vp_rows)

            vf_kv, vp_kv, key_map, prefix_warnings = _normalize_vf_vp_kv(
                vf_kv=vf_kv_raw, vp_kv=vp_kv_raw
            )

            # Update resolved_params keys to normalized keys for audit readability.
            for row in resolved_params:
                if not isinstance(row, dict):
                    continue
                rk = row.get("key")
                if isinstance(rk, str) and rk in key_map:
                    row["key"] = key_map[rk]

            if prefix_warnings:
                for w in prefix_warnings:
                    print(f"[Tableau][WARN] {w}")

            entry = _get_entry_for_view_luid(view_id)
            if not entry:
                raise ValueError(f"未在 registry.db 找到 view_luid 对应条目：{view_id}")
            spec_ref, spec = _resolve_spec_for_entry(entry)
            contract_warnings = _validate_against_runtime_spec(
                spec_key=spec_ref, vf_kv=vf_kv, vp_kv=vp_kv
            )

            for row in resolved_params:
                if not isinstance(row, dict):
                    continue
                key = row.get("key")
                source_bucket = row.get("source")
                if isinstance(key, str) and source_bucket == "vf" and key in vf_kv:
                    row["normalized_value"] = vf_kv[key]
                if isinstance(key, str) and source_bucket == "vp" and key in vp_kv:
                    row["normalized_value"] = vp_kv[key]
        except (ValueError, FileNotFoundError) as e:
            return {
                "success": False,
                "error_code": "CONTRACT_VALIDATION_FAILED",
                "error": str(e),
                "resolved_params": resolved_params,
            }

        if contract_warnings:
            print(f"[Tableau][WARN] Contract warnings: {contract_warnings}")

        # Tableau REST /views/{id}/data 的 vf 参数名通常要求使用“视图字段名”。
        # 我们的 filters spec 里 key 是“业务键”，tableau_field 是“视图字段名”。
        # 若直接使用 key（例如 代理_区域）会导致过滤不生效，进而断言失败。
        spec_filters = (spec.get("filters") or []) + (spec.get("parameters") or [])
        spec_by_key = {
            str(f.get("key")): f
            for f in spec_filters
            if isinstance(f, dict) and isinstance(f.get("key"), (str, int))
        }

        filter_params: dict[str, str] = {":refresh": "yes"}
        user_vf_filters: dict[str, str] = {}
        user_vp_params: dict[str, str] = {}
        for key, value in vf_kv.items():
            f = spec_by_key.get(key) or {}
            tableau_field = f.get("tableau_field") if isinstance(f, dict) else None
            param_key = str(tableau_field).strip() if isinstance(tableau_field, str) else key
            filter_params[f"vf_{param_key}"] = value
            user_vf_filters[key] = value

        for key, value in vp_kv.items():
            f = spec_by_key.get(key) or {}
            tableau_field = f.get("tableau_field") if isinstance(f, dict) else None
            param_key = str(tableau_field).strip() if isinstance(tableau_field, str) else key
            # tbi 环境：参数也必须使用 vf_ 前缀（与 filters 一致）
            filter_params[f"vf_{param_key}"] = value
            user_vp_params[key] = value

        filters = ""
        if filter_params:
            filters = "?" + urlencode(filter_params)
            print(f"[Tableau] 应用筛选器: {filter_params}")

        data_url = f"{auth.api_base}/views/{view_id}/data{filters}"
        api_url_clean = data_url.split("?")[0] + (
            f"?{urlencode({**user_vf_filters, **user_vp_params})}"
            if (user_vf_filters or user_vp_params)
            else ""
        )
        print(f"[Tableau] 导出 CSV (URL: {data_url})...")

        try:
            resp = _request_with_retry(
                data_url,
                auth.get_headers(),
                view_id,
                timeout=120,
                session=auth.session,
            )
        except Exception as e:
            return {"success": False, "error": f"导出异常: {str(e)}"}

        if not resp or resp.status_code != 200:
            error_msg = f"导出失败: {resp.status_code if resp else 'No response'}"
            return {"success": False, "error": error_msg}

        csv_content = resp.content.decode("utf-8", errors="ignore")
        csv_path.write_text(csv_content, encoding="utf-8")
        # Post-export assertions
        profile_dir = Path(output_dir) / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        assertion_success, assertion_report = _perform_assertions(
            csv_path, spec_ref, resolved_params, view_id, view_name
        )

        # Perform time window validation
        time_window_valid = True
        if time_field and time_window:
            expected_windows = [w.strip() for w in time_window.split(",") if w.strip()]
            try:
                with open(csv_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    time_values = [row[time_field] for row in reader if row.get(time_field)]

                if time_values:
                    actual_min = min(time_values)
                    actual_max = max(time_values)
                    time_window_valid = (
                        actual_min in expected_windows and actual_max in expected_windows
                    )
                    assertion_report["time_window"] = {
                        "field": time_field,
                        "expected": expected_windows,
                        "actual_min": actual_min,
                        "actual_max": actual_max,
                        "valid": time_window_valid,
                    }
                else:
                    print(
                        f"[Tableau][WARN] Time field '{time_field}' not found in CSV or has no values"
                    )
                    time_window_valid = False
            except Exception as e:
                print(f"[Tableau][WARN] Failed to perform time window validation: {e}")
                time_window_valid = False

        (profile_dir / "assertions.json").write_text(
            json.dumps(assertion_report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not assertion_success:
            return {
                "success": False,
                "error_code": "ASSERTION_FAILED",
                "error": f"断言失败: {assertion_report['failed_checks']}",
                "failed_checks": assertion_report["failed_checks"],
                "resolved_params": resolved_params,
                "time_window_valid": time_window_valid,
            }

        if not dataset_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = view_name.replace(" ", "_").replace("-", "_")[:20]
            dataset_id = f"ds_{safe_name}_{timestamp}".lower()

        entry = _get_entry_for_view_luid(view_id)
        entry_tableau = entry.get("tableau") if isinstance(entry, dict) else {}
        metadata = dict(tableau_metadata or {})
        if isinstance(entry_tableau, dict):
            metadata.setdefault("workbook_name", str(entry_tableau.get("workbook_name") or ""))
            metadata.setdefault("content_url", str(entry_tableau.get("content_url") or ""))
        metadata.setdefault("view_name", view_name)
        if not metadata.get("page_url"):
            metadata["page_url"] = _build_tableau_page_url(
                base_url=os.environ.get("TABLEAU_BASE_URL", ""),
                site_content_url=os.environ.get("TABLEAU_SITE_ID", ""),
                content_url=str(metadata.get("content_url") or ""),
            )

        manifest = build_manifest(
            csv_content,
            view_url,
            view_id,
            dataset_id,
            source_key=source_key or "",
            display_name=source_display_name or view_name,
            api_url=api_url_clean,
            filters=user_vf_filters,
            tableau_metadata=metadata,
        )

        # Keep parameters separate from filters to avoid downstream misclassification.
        manifest["parameters"] = user_vp_params

        # Persist resolved params for downstream audit (email, dashboards).
        manifest["resolved_params"] = resolved_params
        if contract_warnings:
            manifest["contract_warnings"] = contract_warnings
        # manifest 输出到 profile/ 子目录
        profile_dir = Path(output_dir) / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = profile_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        row_count = manifest["row_count"]
        col_count = len(manifest["schema"]["columns"])
        print(f"[Tableau] 导出完成: {csv_path} ({row_count} 行, {col_count} 列)")
        print(f"[Tableau] Manifest: {manifest_path}")

        pivot_path: str | None = None
        pivot_warning: str | None = None
        pivot_content, pivot_warning, suggested_filename = pivot_long_to_wide(csv_content)
        if pivot_content:
            if output_name:
                # 兼容中文和英文前缀
                if output_name.startswith("原始_"):
                    pivot_filename = f"交叉_{output_name[3:]}.csv"
                elif output_name.startswith("raw_"):
                    pivot_filename = f"pivot_{output_name[4:]}.csv"
                else:
                    pivot_filename = f"交叉_{output_name}.csv"
            elif suggested_filename:
                # 使用工具感知的业务命名
                pivot_filename = suggested_filename
            else:
                pivot_filename = "pivot.csv"

            # 如果提供了 dataset_id 且没有 output_name，使用 dataset_id 作为前缀防止覆盖
            if not output_name and dataset_id and not suggested_filename:
                pivot_filename = f"pivot_{dataset_id}.csv"

            pivot_file = data_dir / pivot_filename
            pivot_file.write_text(pivot_content, encoding="utf-8")
            pivot_path = str(pivot_file)
            pivot_rows = len(pivot_content.strip().split("\n")) - 1
            print(f"[Tableau] Pivot 表: {pivot_file} ({pivot_rows} 行)")
        elif pivot_warning:
            print(f"[Tableau] Pivot 跳过: {pivot_warning}")

        return {
            "success": True,
            "dataset_id": dataset_id,
            "view_name": view_name,
            "tableau": metadata,
            "csv_path": str(csv_path),
            "pivot_path": pivot_path,
            "pivot_warning": pivot_warning,
            "manifest_path": str(manifest_path),
            "row_count": row_count,
            "column_count": col_count,
            "resolved_params": resolved_params,
            "time_window_valid": time_window_valid,
        }
    finally:
        if own_auth:
            auth.signout()


def sanitize_name(name: str) -> str:
    """Sanitize view name for file naming.

    Replaces spaces with underscores and removes special characters.

    Args:
        name: Original view name

    Returns:
        Sanitized name safe for file system
    """
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def export_domain(
    domain_key: str,
    output_dir: str,
    vf_filters: list[str] | None = None,
    vp_filters: list[str] | None = None,
    time_field: str | None = None,
    time_window: str | None = None,
) -> dict[str, Any]:
    """Export all views in a domain with parallel execution.

    Args:
        domain_key: Domain key from registry.db (e.g., "domain.example_dashboard")
        output_dir: Base output directory
        vf_filters: Optional list of filters in "field=value" format
    """
    config = get_domain_config(domain_key)

    # get_domain_config exits on error, but check for safety
    views = config.get("views", [])
    if not views:
        return {
            "success": False,
            "error": f"Domain '{domain_key}' has no views configured",
        }

    domain_name = config.get("display_name", domain_key)
    results = []

    print(f"[Domain] 开始批量导出: {domain_name} ({len(views)} 个视图)")

    auth = get_auth()
    try:
        auth.signin()
    except Exception as e:
        return {"success": False, "error": f"Domain auth failed: {e}"}

    try:
        max_workers = _get_max_concurrent()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for view in views:
                view_name_sanitized = sanitize_name(view["display_name"])
                future = executor.submit(
                    export_view,
                    view_url=view["key"],
                    output_dir=output_dir,
                    view_luid=view["view_luid"],
                    vf_filters=vf_filters,
                    vp_filters=vp_filters,
                    output_name=view_name_sanitized,
                    auth=auth,
                    time_field=time_field,
                    time_window=time_window,
                )
                futures[future] = view

            for future in as_completed(futures):
                view = futures[future]
                try:
                    result = future.result()
                    results.append({"view": view, "result": result})
                    if result.get("success"):
                        print(f"[Domain] ✓ {view['display_name']}")
                    else:
                        print(
                            f"[Domain] ✗ {view['display_name']}: {result.get('error', 'Unknown error')}"
                        )
                except Exception as e:
                    error_result = {"success": False, "error": str(e)}
                    results.append({"view": view, "result": error_result})
                    print(f"[Domain] ✗ {view['display_name']}: {str(e)}")
    finally:
        auth.signout()

    succeeded = sum(1 for r in results if r["result"].get("success"))
    failed = len(results) - succeeded

    print(f"[Domain] 导出完成: {succeeded}/{len(views)} 成功, {failed} 失败")

    # Build export summary
    summary_views = []
    for r in results:
        view = r["view"]
        result = r["result"]
        view_entry = {
            "key": view["key"],
            "display_name": view["display_name"],
            "status": "success" if result.get("success") else "failed",
        }
        if result.get("success"):
            # Extract file path from result (relative to output_dir)
            file_path = result.get("file_path", "")
            view_entry["file_path"] = file_path
        else:
            view_entry["error"] = result.get("error", "Unknown error")
        summary_views.append(view_entry)

    export_summary = {
        "domain_key": domain_key,
        "display_name": domain_name,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "views_total": len(views),
        "views_success": succeeded,
        "views_failed": failed,
        "views": summary_views,
    }

    # Write export_summary.json
    summary_path = Path(output_dir) / "export_summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(export_summary, f, ensure_ascii=False, indent=2)
        print(f"[Domain] 导出清单已生成: {summary_path}")
    except Exception as e:
        print(f"[Domain] 警告: 无法生成导出清单: {e}")

    return {
        "success": True,
        "domain_name": domain_name,
        "total": len(views),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Tableau view data to CSV")
    parser.add_argument("view_url", help="Tableau view URL or name")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--dataset-id", help="Optional dataset ID")
    parser.add_argument("--job-id", help="Job ID for export budget tracking")

    # Mutually exclusive group for view-luid and domain
    view_group = parser.add_mutually_exclusive_group()
    view_group.add_argument("--view-luid", help="View LUID (skip lookup)")
    view_group.add_argument("--domain", help="Domain key from registry.db")

    parser.add_argument(
        "--vf",
        action="append",
        dest="vf_filters",
        metavar="FIELD=VALUE",
        help="View filter (can be used multiple times)",
    )
    parser.add_argument(
        "--vp",
        action="append",
        dest="vp_filters",
        metavar="PARAM=VALUE",
        help="View parameter (can be used multiple times)",
    )
    parser.add_argument(
        "--output-name",
        help="Output file base name (e.g. 原始_区域销售_2025Q4_上海)",
    )
    parser.add_argument("--time-field", help="时间字段名（如 '出票日期年月'）")
    parser.add_argument(
        "--time-window", help="期望的时间窗口值列表（逗号分隔，如 '202510,202511,202512'）"
    )
    args = parser.parse_args()

    if not args.job_id:
        print(
            json.dumps(
                {"success": False, "error": "JOB_ID_REQUIRED"},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    budget_path = _export_budget_path(args.job_id)
    budget = _load_export_budget(budget_path)
    max_count = budget.get("max_count", 2)
    used_count = budget.get("used_count", 0)
    try:
        max_count = int(max_count)
    except (TypeError, ValueError):
        max_count = 2
    try:
        used_count = int(used_count)
    except (TypeError, ValueError):
        used_count = 0

    if used_count >= max_count:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "EXPORT_BUDGET_EXCEEDED",
                    "used": used_count,
                    "max": max_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    result: dict[str, Any]
    success = False
    try:
        if args.domain:
            result = export_domain(
                args.domain,
                args.output_dir,
                args.vf_filters,
                args.vp_filters,
                time_field=args.time_field,
                time_window=args.time_window,
            )
        else:
            result = export_view(
                args.view_url,
                args.output_dir,
                args.dataset_id,
                args.view_luid,
                args.vf_filters,
                args.vp_filters,
                args.output_name,
                time_field=args.time_field,
                time_window=args.time_window,
            )
        success = bool(result.get("success"))
    except Exception as e:
        result = {"success": False, "error": str(e)}
        success = False
    finally:
        _record_export_budget(
            budget_path,
            budget,
            success=success,
            view_luid=args.view_luid,
            domain_key=args.domain,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

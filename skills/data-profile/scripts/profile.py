#!/usr/bin/env python3
"""
通用数据画像脚本 - 领域无关的语义识别系统

两层类型系统：物理类型 + 语义类型
每个语义推断都有置信度和证据
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    for candidate in [start.parent, *start.parents]:
        if (candidate / "runtime").is_dir() and (
            (candidate / ".agents" / "skills").is_dir() or (candidate / "skills").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_ROOT = _find_workspace_root(Path(__file__).resolve())
for bootstrap_path in (WORKSPACE_ROOT / "lib", WORKSPACE_ROOT / "runtime"):
    if str(bootstrap_path) not in sys.path:
        sys.path.insert(0, str(bootstrap_path))
from log_utils import get_log_file, log as base_log, reset_log, stage_logger  # type: ignore
from runtime_config_store import load_document  # type: ignore[import-not-found]



def log(output_dir: str, msg: str) -> None:
    base_log(output_dir, "Profile", msg)


def _col_series(df: pd.DataFrame, col: Any) -> pd.Series:  # type: ignore[type-arg]
    """Get a Series for a single column label (type-stable for checkers)."""
    s = df[col]
    if isinstance(s, pd.DataFrame):
        return s.iloc[:, 0]
    return s


def _scalar_float(v: Any) -> float:  # type: ignore[type-arg]
    """Convert pandas scalar/Series-like values into float."""
    if isinstance(v, pd.Series):
        if len(v) == 0:
            return 0.0
        return float(v.iloc[0])
    return float(v)


def _load_metrics_config(output_dir: str) -> dict[str, Any]:
    """
    加载 metrics 配置。

    Returns:
        包含 field_mapping 和 categories 的配置字典，加载失败返回空字典
    """
    try:
        config = load_document("metrics")
        if isinstance(config, dict) and config:
            log(output_dir, f"已加载业务配置: {WORKSPACE_ROOT / 'runtime' / 'registry.db'}")
            return config
    except Exception as e:
        log(output_dir, f"加载 runtime registry 业务配置失败: {e}")

    log(output_dir, "未找到 metrics 配置，跳过业务语义注入")
    return {}


def _build_metrics_lookup(metrics_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    构建指标查找表：metric_id -> {name_cn, definition, unit, ...}

    遍历 categories 下所有分类的指标列表，提取关键信息。
    """
    lookup: dict[str, dict[str, Any]] = {}

    categories = metrics_config.get("categories", {})
    for category_key, category_data in categories.items():
        if not isinstance(category_data, dict):
            continue
        for group_key, group_data in category_data.items():
            if group_key in ("name", "description"):
                continue
            if not isinstance(group_data, list):
                continue
            for metric in group_data:
                if not isinstance(metric, dict) or "id" not in metric:
                    continue
                metric_id = metric["id"]
                lookup[metric_id] = {
                    "name_cn": metric.get("name_cn", ""),
                    "definition": metric.get("definition", ""),
                    "unit": metric.get("unit", ""),
                    "formula": metric.get("formula", ""),
                    "direction": metric.get("direction", ""),
                    "priority": metric.get("priority", 99),
                }

    return lookup


def infer_physical_type(series: pd.Series) -> str:  # type: ignore[type-arg]
    if pd.api.types.is_numeric_dtype(series):
        if pd.api.types.is_integer_dtype(series):
            return "integer"
        return "float"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    elif pd.api.types.is_bool_dtype(series):
        return "boolean"
    else:
        try:
            sample = series.dropna().head(10)
            if len(sample) > 0:
                parsed = pd.to_datetime(sample, format="mixed", errors="coerce")
                if parsed.notna().all():
                    return "date_string"
        except Exception:
            pass
        return "string"


SEMANTIC_TYPES = {
    "identifier": "唯一标识符",
    "datetime": "日期时间",
    "money": "货币金额",
    "percentage": "百分比/比率",
    "count": "计数/数量",
    "category": "分类变量",
    "ordinal": "序数/等级",
    "delta": "变化量",
    "rate": "转化率/完成率",
    "geo": "地理信息",
    "email": "电子邮件",
    "url": "网址",
    "phone": "电话号码",
    "free_text": "自由文本",
    "technical": "技术/校验字段 (Ignored)",
}

TECHNICAL_SUFFIXES = ["_校验列", "_check", "_validate", "_flag", "_luid", "_id"]


def infer_semantic_candidates(
    col_name: str,
    series: pd.Series,
    physical_type: str,
    stats: dict[str, Any],  # type: ignore[type-arg]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    col_lower = col_name.lower()

    # 优先检测技术字段
    for suffix in TECHNICAL_SUFFIXES:
        if col_lower.endswith(suffix):
            # 特例：如果是业务明确的 Flag (需结合上下文，这里先保守标记为 technical，但 confidence 设为 0.95)
            # 用户可以在分析脚本中如果确实需要再 override，但默认应该忽略
            candidates.append(
                {
                    "type": "technical",
                    "confidence": 0.99,
                    "evidence": {"suffix_match": suffix},
                    "tags": ["ignored", "etl_artifact"],
                }
            )
            # 一旦判定为 technical，通常不再推断其他类型，或者排在第一位
            return candidates

    # 字段名强提示：即使不唯一，也可能是业务标识字段（例如 IATA 航协号）
    id_name_keywords = ["iata", "航协", "编号", "代码", " id", "_id", "id_"]
    if any(kw in col_lower for kw in id_name_keywords):
        candidates.append(
            {
                "type": "identifier",
                "confidence": 0.9,
                "evidence": {"column_name_hint": True},
            }
        )

    money_keywords = [
        "price",
        "cost",
        "revenue",
        "amount",
        "fee",
        "salary",
        "pay",
        "income",
        "价格",
        "金额",
        "收入",
        "费用",
        "薪资",
        "工资",
        "成本",
        "营收",
        "客单价",
        "利润",
        "毛利",
        "收益",
        "贡献",
    ]
    has_money_keyword = any(kw in col_lower for kw in money_keywords)

    n_rows = len(series)
    n_unique = series.nunique()
    uniqueness_ratio = n_unique / n_rows if n_rows > 0 else 0
    sample = series.dropna().head(50).tolist()

    if uniqueness_ratio > 0.9 and n_unique > 10:
        # 数值型金额/收益字段天然高基数，不能因为几乎每行都不同就误判成 identifier
        if not (physical_type in ("integer", "float") and has_money_keyword):
            confidence = min(0.95, uniqueness_ratio)
            candidates.append(
                {
                    "type": "identifier",
                    "confidence": round(confidence, 2),
                    "evidence": {
                        "uniqueness_ratio": round(uniqueness_ratio, 3),
                        "unique_count": n_unique,
                    },
                }
            )

    if physical_type in ("datetime", "date_string"):
        candidates.append(
            {"type": "datetime", "confidence": 0.95, "evidence": {"physical_type": physical_type}}
        )

    date_keywords = [
        "date",
        "time",
        "日期",
        "时间",
        "month",
        "year",
        "月",
        "年",
        "day",
        "日",
        "week",
        "周",
    ]
    if any(kw in col_lower for kw in date_keywords):
        if not any(c["type"] == "datetime" for c in candidates):
            candidates.append(
                {"type": "datetime", "confidence": 0.7, "evidence": {"column_name_hint": True}}
            )

    if physical_type in ("integer", "float"):
        if has_money_keyword:
            candidates.append(
                {"type": "money", "confidence": 0.9, "evidence": {"column_name_hint": True}}
            )

        if physical_type == "float" and sample:
            decimal_pattern = [
                abs(v - round(v, 2)) < 0.001 for v in sample if isinstance(v, (int, float))
            ]
            if decimal_pattern and sum(decimal_pattern) / len(decimal_pattern) > 0.8:
                if not any(c["type"] == "money" for c in candidates):
                    candidates.append(
                        {
                            "type": "money",
                            "confidence": 0.6,
                            "evidence": {
                                "two_decimal_ratio": round(
                                    sum(decimal_pattern) / len(decimal_pattern), 2
                                )
                            },
                        }
                    )

    if physical_type in ("integer", "float"):
        pct_keywords = ["rate", "ratio", "percent", "pct", "率", "比", "占比", "比例"]
        if any(kw in col_lower for kw in pct_keywords):
            candidates.append(
                {"type": "percentage", "confidence": 0.9, "evidence": {"column_name_hint": True}}
            )

        if sample:
            numeric_sample = [v for v in sample if isinstance(v, (int, float)) and not np.isnan(v)]
            if numeric_sample:
                min_val, max_val = min(numeric_sample), max(numeric_sample)
                if 0 <= min_val and max_val <= 1:
                    if not any(c["type"] == "percentage" for c in candidates):
                        candidates.append(
                            {
                                "type": "percentage",
                                "confidence": 0.75,
                                "evidence": {"value_range": f"{min_val:.2f}-{max_val:.2f}"},
                            }
                        )
                elif 0 <= min_val and max_val <= 100:
                    mean_val = sum(numeric_sample) / len(numeric_sample)
                    if mean_val < 100:
                        if not any(c["type"] == "percentage" for c in candidates):
                            candidates.append(
                                {
                                    "type": "percentage",
                                    "confidence": 0.5,
                                    "evidence": {"value_range": f"{min_val:.2f}-{max_val:.2f}"},
                                }
                            )

    if physical_type == "integer":
        count_keywords = [
            "count",
            "num",
            "qty",
            "quantity",
            "total",
            "sum",
            "数",
            "量",
            "人数",
            "次数",
            "个数",
            "班次",
            "订单数",
        ]
        if any(kw in col_lower for kw in count_keywords):
            candidates.append(
                {"type": "count", "confidence": 0.85, "evidence": {"column_name_hint": True}}
            )

        if sample:
            numeric_sample = [v for v in sample if isinstance(v, (int, float)) and not np.isnan(v)]
            if numeric_sample and all(v >= 0 and v == int(v) for v in numeric_sample):
                if not any(c["type"] == "count" for c in candidates):
                    candidates.append(
                        {
                            "type": "count",
                            "confidence": 0.5,
                            "evidence": {"all_positive_integers": True},
                        }
                    )

    delta_keywords = [
        "delta",
        "change",
        "diff",
        "growth",
        "increase",
        "decrease",
        "同比",
        "环比",
        "增长",
        "变化",
        "涨幅",
        "跌幅",
        "yoy",
        "mom",
        "qoq",
    ]
    if any(kw in col_lower for kw in delta_keywords):
        candidates.append(
            {"type": "delta", "confidence": 0.9, "evidence": {"column_name_hint": True}}
        )

    if physical_type in ("integer", "float") and sample:
        numeric_sample = [v for v in sample if isinstance(v, (int, float)) and not np.isnan(v)]
        if numeric_sample:
            has_positive = any(v > 0 for v in numeric_sample)
            has_negative = any(v < 0 for v in numeric_sample)
            if has_positive and has_negative:
                if not any(c["type"] == "delta" for c in candidates):
                    candidates.append(
                        {
                            "type": "delta",
                            "confidence": 0.6,
                            "evidence": {"has_positive_and_negative": True},
                        }
                    )

    if physical_type == "string" and 2 <= n_unique <= 100:
        confidence = 0.8 if n_unique <= 20 else 0.6
        candidates.append(
            {"type": "category", "confidence": confidence, "evidence": {"unique_count": n_unique}}
        )

    ordinal_keywords = [
        "level",
        "grade",
        "rank",
        "tier",
        "priority",
        "score",
        "等级",
        "级别",
        "评分",
        "优先级",
        "层级",
    ]
    if any(kw in col_lower for kw in ordinal_keywords):
        candidates.append(
            {"type": "ordinal", "confidence": 0.8, "evidence": {"column_name_hint": True}}
        )

    geo_keywords = [
        "city",
        "country",
        "state",
        "province",
        "region",
        "address",
        "location",
        "城市",
        "国家",
        "省",
        "地区",
        "地址",
        "位置",
        "区域",
    ]
    if any(kw in col_lower for kw in geo_keywords):
        candidates.append(
            {"type": "geo", "confidence": 0.85, "evidence": {"column_name_hint": True}}
        )

    if physical_type == "string" and sample:
        str_sample = [str(v) for v in sample if v is not None]

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        email_matches = sum(1 for v in str_sample if re.match(email_pattern, v))
        if str_sample and email_matches / len(str_sample) > 0.8:
            candidates.append(
                {
                    "type": "email",
                    "confidence": 0.95,
                    "evidence": {"pattern_match_ratio": round(email_matches / len(str_sample), 2)},
                }
            )

        url_pattern = r"^https?://"
        url_matches = sum(1 for v in str_sample if re.match(url_pattern, v))
        if str_sample and url_matches / len(str_sample) > 0.8:
            candidates.append(
                {
                    "type": "url",
                    "confidence": 0.95,
                    "evidence": {"pattern_match_ratio": round(url_matches / len(str_sample), 2)},
                }
            )

        phone_pattern = r"^[\d\-\+\(\)\s]{7,20}$"
        phone_matches = sum(1 for v in str_sample if re.match(phone_pattern, v))
        if str_sample and phone_matches / len(str_sample) > 0.8:
            candidates.append(
                {
                    "type": "phone",
                    "confidence": 0.7,
                    "evidence": {"pattern_match_ratio": round(phone_matches / len(str_sample), 2)},
                }
            )

    if physical_type == "string" and sample:
        str_sample = [str(v) for v in sample if v is not None]
        avg_length = sum(len(v) for v in str_sample) / len(str_sample) if str_sample else 0
        if avg_length > 50 and uniqueness_ratio > 0.5:
            candidates.append(
                {
                    "type": "free_text",
                    "confidence": 0.7,
                    "evidence": {
                        "avg_length": round(avg_length, 1),
                        "uniqueness_ratio": round(uniqueness_ratio, 2),
                    },
                }
            )

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates


def determine_column_role(
    col_name: str,
    physical_type: str,
    semantic_candidates: list[dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    top_semantic = semantic_candidates[0]["type"] if semantic_candidates else None

    # 字段名强提示：标识字段优先（即使是数字列也不当作 metric）
    if any(k in col_name for k in ["IATA", "航协号", "编号", "代码", "ID", "Id", "id"]):
        return "identifier"

    if top_semantic == "identifier":
        return "identifier"

    if top_semantic == "datetime" or physical_type in ("datetime", "date_string"):
        return "datetime"

    if physical_type in ("integer", "float"):
        return "metric"

    if physical_type == "string":
        n_unique = stats.get("unique_count", 0)
        if 2 <= n_unique <= 100:
            return "dimension"

    return "unknown"


def extract_signals(df: pd.DataFrame, columns_info: list[dict[str, Any]]) -> dict[str, Any]:
    signals: dict[str, Any] = {
        "has_datetime": False,
        "has_delta_columns": False,
        "high_concentration": False,
        "has_anomaly_candidates": False,
        "has_correlation_candidates": False,
        "has_strong_corr_candidate": False,
        "cross_section_only": True,
    }

    metric_cols = []
    dimension_cols = []
    datetime_cols = []
    delta_cols = []

    for col_info in columns_info:
        role = col_info.get("role", "unknown")
        if role == "metric":
            metric_cols.append(col_info["name"])
        elif role == "dimension":
            dimension_cols.append(col_info["name"])
        elif role == "datetime":
            datetime_cols.append(col_info["name"])

        semantic_candidates = col_info.get("semantic_candidates", [])
        for sc in semantic_candidates:
            if sc.get("type") == "delta" and sc.get("confidence", 0) >= 0.6:
                delta_cols.append(col_info["name"])
                break

    signals["has_datetime"] = len(datetime_cols) > 0
    signals["cross_section_only"] = len(datetime_cols) == 0
    signals["has_delta_columns"] = len(delta_cols) > 0
    signals["metric_count"] = len(metric_cols)
    signals["dimension_count"] = len(dimension_cols)

    for dim_col in dimension_cols[:3]:
        if dim_col in df.columns:
            vc = df[dim_col].value_counts()
            if len(vc) >= 3:
                top3_share = vc.head(3).sum() / vc.sum()
                if top3_share > 0.5:
                    signals["high_concentration"] = True
                    signals["concentration_detail"] = {
                        "column": dim_col,
                        "top3_share": round(float(top3_share), 3),
                    }
                    break

    signals["has_correlation_candidates"] = len(metric_cols) >= 3
    signals["has_anomaly_candidates"] = len(datetime_cols) > 0 and len(metric_cols) > 0

    if len(metric_cols) >= 2 and len(df) >= 30:
        try:
            metric_df = df[metric_cols].dropna()
            if len(metric_df) >= 30:
                corr_matrix = metric_df.corr(method="pearson").abs()  # type: ignore[arg-type]
                np.fill_diagonal(corr_matrix.values, 0)
                max_corr = corr_matrix.max().max()
                signals["has_strong_corr_candidate"] = float(max_corr) >= 0.7
        except Exception:
            pass

    return signals


def profile_data(csv_path: str, output_dir: str) -> dict[str, Any]:
    # 创建 profile 子目录，所有 profiling 输出放到 profile/ 下
    profile_dir = Path(output_dir) / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    reset_log(output_dir)

    log(output_dir, f"开始数据画像: {csv_path}")

    # 加载 runtime registry 获取业务语义映射
    metrics_config = _load_metrics_config(output_dir)
    field_mapping = metrics_config.get("field_mapping", {})
    metrics_definitions = _build_metrics_lookup(metrics_config)

    df = pd.read_csv(csv_path, encoding="utf-8")
    log(output_dir, f"数据加载: {len(df)} 行 × {len(df.columns)} 列")

    columns_schema: list[dict[str, Any]] = []

    for col in df.columns:
        series = _col_series(df, col)

        physical_type = infer_physical_type(series)  # type: ignore[arg-type]

        stats = {
            "unique_count": int(series.nunique()),
            "missing_count": int(series.isnull().sum()),
            "missing_pct": round(float(series.isnull().sum()) / len(df) * 100, 2)
            if len(df) > 0
            else 0,
        }

        semantic_candidates = infer_semantic_candidates(col, series, physical_type, stats)  # type: ignore[arg-type]
        role = determine_column_role(col, physical_type, semantic_candidates, stats)

        col_info: dict[str, Any] = {
            "name": col,
            "physical_type": physical_type,
            "semantic_candidates": semantic_candidates,
            "role": role,
            "stats": stats,
        }

        if semantic_candidates:
            col_info["semantic_type"] = semantic_candidates[0]["type"]
            col_info["semantic_confidence"] = semantic_candidates[0]["confidence"]

        if col in field_mapping:
            business_id = field_mapping[col]
            col_info["business_id"] = business_id
            if business_id in metrics_definitions:
                metric_def = metrics_definitions[business_id]
                col_info["business_name"] = metric_def.get("name_cn", "")
                col_info["business_definition"] = metric_def.get("definition", "")
                col_info["business_unit"] = metric_def.get("unit", "")

                # 业务映射命中的数值字段，默认应优先保留 metric 角色；
                # 若被高基数误判成 identifier，则按业务单位回正语义类型。
                if physical_type in ("integer", "float"):
                    col_info["role"] = "metric"
                    business_unit = str(metric_def.get("unit", ""))
                    business_name = str(metric_def.get("name_cn", ""))
                    if (
                        col_info.get("semantic_type") == "identifier"
                        and (
                            "元" in business_unit
                            or "%" in business_unit
                            or any(k in business_name for k in ["收入", "利润", "成本", "客单价", "转化率", "单位收入"])
                        )
                    ):
                        semantic_type = "percentage" if "%" in business_unit else "money"
                        col_info["semantic_candidates"] = [
                            {
                                "type": semantic_type,
                                "confidence": 0.96,
                                "evidence": {"business_mapping": business_id},
                            }
                        ] + col_info["semantic_candidates"]
                        col_info["semantic_type"] = semantic_type
                        col_info["semantic_confidence"] = 0.96

        columns_schema.append(col_info)

        semantic_str = (
            f" -> {semantic_candidates[0]['type']}({semantic_candidates[0]['confidence']:.0%})"
            if semantic_candidates
            else ""
        )
        log(output_dir, f"列 {col}: {physical_type} [{role}]{semantic_str}")

    quality_issues: list[str] = []
    missing_stats: dict[str, dict[str, Any]] = {}
    unique_stats: dict[str, int] = {}

    for col in df.columns:
        col_series = _col_series(df, col)
        missing_count = int(col_series.isnull().sum())
        missing_pct = missing_count / len(df) * 100 if len(df) > 0 else 0
        unique_count = int(col_series.nunique())

        missing_stats[col] = {"count": missing_count, "percentage": round(missing_pct, 2)}
        unique_stats[col] = unique_count

        if missing_pct > 10:
            quality_issues.append(f"列 {col} 缺失率 {missing_pct:.1f}%")
        if unique_count == 1:
            quality_issues.append(f"列 {col} 仅有单一值")

    total_cells = len(df) * len(df.columns)
    missing_cells = int(df.isnull().sum().sum())
    quality_score = round(1 - missing_cells / total_cells, 3) if total_cells > 0 else 1.0

    log(output_dir, f"数据质量分数: {quality_score:.1%}")

    numeric_stats: dict[str, dict[str, Any]] = {}
    for col in df.select_dtypes(include=["int64", "float64"]).columns:
        s = _col_series(df, col).dropna()
        if len(s) > 0:
            numeric_stats[col] = {
                "count": int(len(s)),
                "mean": round(_scalar_float(s.mean()), 2),
                "std": round(_scalar_float(s.std()), 2),
                "min": _scalar_float(s.min()),
                "25%": _scalar_float(s.quantile(0.25)),
                "50%": _scalar_float(s.quantile(0.5)),
                "75%": _scalar_float(s.quantile(0.75)),
                "max": _scalar_float(s.max()),
            }

    categorical_stats: dict[str, dict[str, Any]] = {}
    for col in df.select_dtypes(include=["object"]).columns:
        col_series = _col_series(df, col)
        value_counts = col_series.value_counts()
        categorical_stats[col] = {
            "unique_count": int(col_series.nunique()),
            "top_values": {str(k): int(v) for k, v in value_counts.head(10).to_dict().items()},
        }

    signals = extract_signals(df, columns_schema)
    log(output_dir, f"信号提取: {signals}")

    job_id = os.environ.get("SESSION_ID", Path(output_dir).name)

    # 尝试从 export_budget.json 读取数据源元数据
    source_key = os.environ.get("TABLEAU_SOURCE_KEY")
    view_luid = os.environ.get("TABLEAU_VIEW_LUID")
    display_name = os.environ.get("TABLEAU_DISPLAY_NAME")

    if not view_luid:
        budget_path = Path(output_dir) / "export_budget.json"
        if budget_path.exists():
            try:
                with open(budget_path, encoding="utf-8") as f:
                    budget = json.load(f)
                    if budget.get("history"):
                        last_export = budget["history"][-1]
                        view_luid = last_export.get("view_luid")
                        source_key = last_export.get("domain_key") or source_key
            except Exception:
                pass

    manifest = {
        "id": f"ds_{job_id}",
        "source_key": source_key,
        "view_luid": view_luid,
        "display_name": display_name,
        "source_type": "csv",
        "source_ref": csv_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(df),
        "column_count": len(df.columns),
        "schema": {"columns": columns_schema},
        "profile_summary": {
            "quality_score": quality_score,
            "missing_values": {
                col: missing_stats[col]["count"]
                for col in df.columns
                if missing_stats[col]["count"] > 0
            },
        },
        "lineage": {"source": "profiling_skill", "transforms": []},
    }

    manifest_path = profile_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(output_dir, "profile/manifest.json 已生成")

    profile = {
        "job_id": job_id,
        "profiled_at": datetime.now().isoformat(),
        "data_file": csv_path,
        "data_summary": {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        },
        "schema": columns_schema,
        "signals": signals,
        "quality": {
            "score": quality_score,
            "issues": quality_issues,
            "missing_stats": missing_stats,
            "unique_stats": unique_stats,
        },
        "statistics": {"numeric": numeric_stats, "categorical": categorical_stats},
    }

    profile_path = profile_dir / "profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    log(output_dir, "profile/profile.json 已生成")

    log(
        output_dir,
        f"数据画像完成: {len(df)} 行, {len(df.columns)} 列, 质量 {quality_score:.1%}",
    )

    return {
        "success": True,
        "manifest_path": str(manifest_path),
        "profile_path": str(profile_path),
        "row_count": len(df),
        "column_count": len(df.columns),
        "quality_score": quality_score,
        "signals": signals,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成 profile/manifest.json 与 profile/profile.json 的数据画像结果。",
    )
    parser.add_argument("data_csv", nargs="?", help="输入数据文件路径")
    parser.add_argument("output_dir", nargs="?", help="输出目录（产物写入 profile/ 子目录）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.data_csv or not args.output_dir:
        parser.error("the following arguments are required: data_csv, output_dir")

    log_buffer = io.StringIO()
    with redirect_stdout(log_buffer):
        result = profile_data(args.data_csv, args.output_dir)

    log_output = log_buffer.getvalue()
    if log_output:
        get_log_file(args.output_dir).write_text(log_output, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

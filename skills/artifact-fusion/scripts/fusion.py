#!/usr/bin/env python3
import sys
import json
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def fusion(input_paths: list[str], output_path: str, strategy: str) -> dict[str, Any]:
    # 智能处理：支持输出目录或直接输出 CSV 文件路径
    out_p = Path(output_path)
    if out_p.suffix.lower() == ".csv":
        output_dir = out_p.parent
        csv_path = out_p
    else:
        output_dir = out_p
        csv_path = out_p / "data.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "fusion_script.log"

    def log_msg(msg: str):
        print(msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")

    log_msg(f"[Fusion] 开始融合: 策略={strategy}, 输入={len(input_paths)} 个数据集")

    datasets = []
    for path_str in input_paths:
        p = Path(path_str)
        # 支持输入目录（含 data.csv）或直接输入 CSV 文件
        if p.is_file() and p.suffix.lower() == ".csv":
            csv_in = p
            manifest_in = p.parent / "manifest.json"
        else:
            csv_in = p / "data.csv"
            manifest_in = p / "manifest.json"

        if not csv_in.exists():
            log_msg(f"[Error] 输入文件不存在: {csv_in}")
            return {"success": False, "error": f"输入文件不存在: {csv_in}"}

        try:
            df = pd.read_csv(csv_in, encoding="utf-8")
        except Exception as e:
            # 尝试回退编码
            try:
                df = pd.read_csv(csv_in, encoding="utf-8-sig")
            except Exception as e2:
                log_msg(f"[Error] 无法读取 CSV {csv_in}: {e2}")
                return {"success": False, "error": f"无法读取 CSV: {e2}"}

        manifest = {}
        if manifest_in.exists():
            try:
                manifest = json.loads(manifest_in.read_text(encoding="utf-8"))
            except Exception:
                pass

        datasets.append({"manifest": manifest, "df": df, "path": path_str})
        log_msg(f"[Fusion] 加载: {manifest.get('id', csv_in.name)} ({len(df)} 行)")

    if not datasets:
        return {"success": False, "error": "无有效输入数据集"}

    try:
        if strategy == "passthrough" or len(datasets) == 1:
            result_df = datasets[0]["df"]
            base_manifest = datasets[0]["manifest"].copy()
            log_msg("[Fusion] 透传模式")

        elif strategy == "union":
            # 宽松 UNION：取列并集，缺失填充 NaN
            result_df = pd.concat([ds["df"] for ds in datasets], ignore_index=True, sort=False)
            base_manifest = datasets[0]["manifest"].copy()
            log_msg(f"[Fusion] UNION: 合并 {len(datasets)} 个数据集")

        elif strategy == "join":
            # 简单水平合并（基于索引或尝试寻找 ID）
            result_df = datasets[0]["df"]
            for i, ds in enumerate(datasets[1:], 1):
                result_df = pd.concat([result_df, ds["df"]], axis=1)
            base_manifest = datasets[0]["manifest"].copy()
            log_msg(f"[Fusion] JOIN (Concat axis=1): 合并 {len(datasets)} 个数据集")

        else:
            log_msg(f"[Error] 未知策略: {strategy}")
            return {"success": False, "error": f"未知策略: {strategy}"}

        # 保存结果
        result_df.to_csv(csv_path, index=False, encoding="utf-8")

        # 生成新 manifest
        base_manifest["id"] = f"ds_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        base_manifest["created_at"] = datetime.now(timezone.utc).isoformat()
        base_manifest["row_count"] = len(result_df)

        new_columns = []
        for col in result_df.columns:
            new_columns.append({"name": str(col), "type": "string"})
        base_manifest["schema"] = {"columns": new_columns}

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(base_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        log_msg(f"[Result] 成功: {csv_path}")
        return {
            "success": True,
            "dataset_id": base_manifest["id"],
            "row_count": len(result_df),
            "csv_path": str(csv_path),
            "manifest_path": str(manifest_path),
        }

    except Exception as e:
        log_msg(f"[Error] 融合失败: {e}")
        return {"success": False, "error": str(e)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Merge multiple datasets.")
    parser.add_argument("strategy", nargs="?", help="Fusion strategy: union/join/passthrough")
    parser.add_argument("output_dir", nargs="?", help="Output directory or file")
    parser.add_argument("input_dirs", nargs="*", help="Input directories or files")

    parser.add_argument("--strategy", dest="s_flag", help="Fusion strategy")
    parser.add_argument("--output", dest="o_flag", help="Output directory/file")
    parser.add_argument("--datasets", nargs="*", help="Input datasets")
    parser.add_argument("--lineage", help="Ignored")

    args = parser.parse_args()

    strategy = args.s_flag or args.strategy
    output_path = args.o_flag or args.output_dir
    input_paths = args.datasets or args.input_dirs

    if not strategy or not output_path or not input_paths:
        print("Usage: python fusion.py <strategy> <output> <input1> [input2] ...")
        sys.exit(1)

    result = fusion(input_paths, output_path, strategy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

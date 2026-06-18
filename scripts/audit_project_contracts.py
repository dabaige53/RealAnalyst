#!/usr/bin/env python3
"""Audit RealAnalyst project contracts across skills, code, metadata, and tests."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - dependency is installed in CI.
    yaml = None  # type: ignore[assignment]


REPO = Path(__file__).resolve().parents[1]
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
FORBIDDEN_DATASET_KEYS = {
    "sample_profile",
    "sample_values",
    "top_values",
    "enum_values",
    "source_mapping",
    "duckdb_type",
    "nullable",
    "definition_source",
}
EXPECTED_PIPELINE_SKILLS = [
    "getting-started",
    "metadata",
    "analysis-run",
    "analysis-plan",
    "data-export",
    "data-profile",
    "report",
    "report-verify",
]
SKILL_DELIVERY_TOKENS = {
    "getting-started": ["doctor.py", "RA:metadata"],
    "metadata": ["context", "registry"],
    "analysis-run": ["job_manifest", "data-export", "data-profile", "report-verify"],
    "analysis-plan": ["analysis_plan", "selected_report_template", "job_manifest"],
    "data-export": ["export_summary", "job_manifest"],
    "data-profile": ["profile/manifest.json", "profile/profile.json", "job_manifest"],
    "report": ["job_manifest", "输出文件清单", "report-verify"],
    "report-verify": ["verification.json", "failed", "passed"],
}
HANDOFF_CONTRACTS = [
    {
        "producer": "getting-started",
        "consumer": "metadata",
        "producer_outputs": [["doctor.py"], ["推荐路径", "metadata 初始化命令"]],
        "consumer_inputs": [["doctor 输出"], ["metadata/sources", "metadata/datasets"]],
        "trigger_or_next_step": [["RA:metadata"]],
        "state_update": [["不创建目录", "不写 metadata"], ["metadata/datasets", "runtime/registry.db"]],
    },
    {
        "producer": "metadata",
        "consumer": "analysis-run",
        "producer_outputs": [["context pack"], ["registry", "index", "context"]],
        "consumer_inputs": [["metadata context"], ["runtime registry"]],
        "trigger_or_next_step": [["RA:analysis-run"]],
        "state_update": [["metadata_index"], ["runtime_registry"], ["export_ready"]],
    },
    {
        "producer": "analysis-run",
        "consumer": "analysis-plan",
        "producer_outputs": [["normalized_request.json"], ["metadata context"]],
        "consumer_inputs": [["normalized_request.json"], ["metadata context pack"]],
        "trigger_or_next_step": [["RA:analysis-plan"]],
        "state_update": [["analysis_plan.md"], ["job_manifest.json"]],
    },
    {
        "producer": "analysis-plan",
        "consumer": "data-export",
        "producer_outputs": [["analysis_plan.md"], ["job_manifest planning"], ["下一步取数动作"]],
        "consumer_inputs": [["source_id"], ["取数字段"], ["过滤条件"], ["SESSION_ID"]],
        "trigger_or_next_step": [["正式取数前"], ["下一步取数动作"]],
        "state_update": [["job_manifest.json"], ["job_manifest"]],
    },
    {
        "producer": "data-export",
        "consumer": "data-profile",
        "producer_outputs": [["正式 CSV"], ["export_summary"], ["duckdb_export_summary"], ["job_manifest"]],
        "consumer_inputs": [["正式 CSV"], ["export_summary.json"], ["duckdb_export_summary.json"], ["SESSION_ID"]],
        "trigger_or_next_step": [["RA:data-profile"]],
        "state_update": [["artifact index 更新"], ["job_manifest 更新"], ["acquisition_log.jsonl"]],
    },
    {
        "producer": "data-profile",
        "consumer": "report",
        "producer_outputs": [["profile/manifest.json"], ["profile/profile.json"], ["job_manifest"]],
        "consumer_inputs": [["profile/manifest.json"], ["profile/profile.json"], ["job_manifest.json"]],
        "trigger_or_next_step": [["RA:report"], ["analysis-run"]],
        "state_update": [["artifact_index.json"], ["job_manifest.json"], ["analysis_journal.md"]],
    },
    {
        "producer": "report",
        "consumer": "report-verify",
        "producer_outputs": [["报告 Markdown"], ["输出文件清单"], ["job_manifest"]],
        "consumer_inputs": [["report_md"], ["analysis_json"], ["data_csv"], ["output_dir"]],
        "trigger_or_next_step": [["RA:report-verify"]],
        "state_update": [["job_manifest.json"], ["verification.json"], ["delivery_manifest.json"]],
    },
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def finding(
    findings: list[dict[str, Any]],
    *,
    severity: str,
    check: str,
    message: str,
    path: Path | str | None = None,
    evidence: str = "",
) -> None:
    findings.append(
        {
            "severity": severity,
            "check": check,
            "path": rel(path) if isinstance(path, Path) else path,
            "message": message,
            "evidence": evidence,
        }
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def audit_test_layout(findings: list[dict[str, Any]]) -> None:
    if not (REPO / "tests").is_dir():
        finding(findings, severity="error", check="test_layout", path="tests", message="缺少唯一代码测试目录 tests/")
    if (REPO / "Test").exists() or (REPO / "test").is_dir():
        finding(
            findings,
            severity="error",
            check="test_layout",
            message="不应存在第二套顶层 Test/test 目录；测试文档应放入 tests/README.md 和 tests/reports/",
        )
    if not (REPO / "tests" / "README.md").is_file():
        finding(
            findings,
            severity="error",
            check="test_layout",
            path="tests/README.md",
            message="缺少测试文档规范 tests/README.md",
        )
    if not (REPO / "tests" / "reports").is_dir():
        finding(
            findings,
            severity="error",
            check="test_layout",
            path="tests/reports",
            message="缺少测试需求报告目录 tests/reports/",
        )
    test_sh = REPO / "test.sh"
    if not test_sh.exists():
        finding(findings, severity="error", check="test_sh", path=test_sh, message="缺少根目录一键测试入口 test.sh")
        return
    script = read_text(test_sh)
    required_tokens = [
        "-m json.tool .codex-plugin/plugin.json",
        "skills/metadata/scripts/metadata.py validate",
        "scripts/audit_project_contracts.py",
        "-m unittest tests.test_ci_workflows",
        "-m unittest discover -s tests",
        "scripts/run_manifest_workflow_regression.py",
        "git diff --check",
    ]
    positions: list[int] = []
    for token in required_tokens:
        if token not in script:
            finding(findings, severity="error", check="test_sh", path=test_sh, message=f"test.sh 缺少测试命令: {token}")
        else:
            positions.append(script.index(token))
    if len(positions) == len(required_tokens) and positions != sorted(positions):
        finding(findings, severity="error", check="test_sh", path=test_sh, message="test.sh 测试命令顺序不符合公开测试入口约定")
    ci = REPO / ".github" / "workflows" / "ci.yml"
    if ci.exists() and "bash test.sh" not in read_text(ci):
        finding(findings, severity="error", check="ci_alignment", path=ci, message="CI 未调用 bash test.sh")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    payload: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload


def audit_skills(findings: list[dict[str, Any]]) -> None:
    skills_dir = REPO / "skills"
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    if not skill_files:
        finding(findings, severity="error", check="skills", path=skills_dir, message="未发现任何 Skill")
        return

    skill_names = {path.parent.name for path in skill_files}
    for expected in EXPECTED_PIPELINE_SKILLS:
        if expected not in skill_names:
            finding(findings, severity="error", check="skill_pipeline", path=skills_dir, message=f"核心交付链缺少 skill: {expected}")

    for skill_file in skill_files:
        skill_dir = skill_file.parent
        text = read_text(skill_file)
        frontmatter = parse_frontmatter(text)
        name = frontmatter.get("name", "")
        description = frontmatter.get("description", "")
        if not name or not description:
            finding(findings, severity="error", check="skill_frontmatter", path=skill_file, message="SKILL.md frontmatter 必须包含 name 和 description")
        normalized_name = name.removeprefix("RA:")
        if name and normalized_name != skill_dir.name:
            finding(
                findings,
                severity="warning",
                check="skill_frontmatter",
                path=skill_file,
                message=f"Skill name 与目录名不一致: {name} != {skill_dir.name}",
            )
        readme = skill_dir / "README.md"
        if not readme.exists():
            finding(findings, severity="warning", check="skill_readme", path=skill_dir, message="Skill 缺少 README.md")
        elif skill_dir.name in EXPECTED_PIPELINE_SKILLS:
            readme_text = read_text(readme)
            if "## 输入与输出" not in readme_text:
                finding(
                    findings,
                    severity="warning",
                    check="skill_readme",
                    path=readme,
                    message="核心交付链 Skill README 缺少“输入与输出”章节",
                )
            if "| 下一步 |" not in readme_text:
                finding(
                    findings,
                    severity="warning",
                    check="skill_readme",
                    path=readme,
                    message="核心交付链 Skill README 缺少下一步交付说明",
                )
            combined = text + "\n" + readme_text
            for token in SKILL_DELIVERY_TOKENS.get(skill_dir.name, []):
                if token not in combined:
                    finding(
                        findings,
                        severity="warning",
                        check="skill_delivery_token",
                        path=skill_dir,
                        message=f"核心交付链 Skill 文档未覆盖关键交付物或下游 token: {token}",
                    )
        completion_count = len(re.findall(r"(?m)^## Completion Summary\b", text))
        if completion_count != 1:
            finding(
                findings,
                severity="warning",
                check="skill_completion_summary",
                path=skill_file,
                message=f"SKILL.md 应有且仅有一个 Completion Summary，当前为 {completion_count}",
            )
        for match in re.finditer(r"(?<![\w.-])([A-Za-z0-9_./-]+\.py)\b", text):
            candidate = match.group(1)
            if candidate.startswith(("http", "/")):
                continue
            path = (skill_dir / candidate).resolve() if not candidate.startswith("skills/") else (REPO / candidate).resolve()
            if "scripts/" in candidate and not path.exists():
                finding(
                    findings,
                    severity="warning",
                    check="skill_script_reference",
                    path=skill_file,
                    message=f"SKILL.md 引用了不存在的脚本: {candidate}",
                )


def audit_python_collection(findings: list[dict[str, Any]]) -> None:
    ignored_roots = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for path in sorted(REPO.glob("**/test_*.py")):
        relative = path.relative_to(REPO)
        if any(part in ignored_roots for part in relative.parts) or relative.parts[0] == "tests":
            continue
        text = read_text(path)
        if "__test__ = False" not in text:
            finding(
                findings,
                severity="error",
                check="pytest_collection",
                path=path,
                message="tests/ 外的 test_*.py 必须设置 __test__ = False，避免被 pytest 误收集",
            )


def audit_schemas(findings: list[dict[str, Any]]) -> None:
    for path in sorted((REPO / "schemas").glob("*.json")):
        try:
            json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            finding(findings, severity="error", check="schema_json", path=path, message="JSON schema 语法错误", evidence=str(exc))


def walk_mapping(value: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        for item in value.values():
            out.extend(walk_mapping(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(walk_mapping(item))
    return out


def audit_metadata(findings: list[dict[str, Any]]) -> None:
    if yaml is None:
        finding(findings, severity="error", check="metadata_yaml", message="PyYAML 不可用，无法审计 metadata YAML")
        return
    dataset_ids: dict[str, Path] = {}

    for path in sorted((REPO / "metadata" / "datasets").glob("*.yaml")):
        try:
            payload = yaml.safe_load(read_text(path))
        except Exception as exc:  # pragma: no cover - defensive reporting.
            finding(findings, severity="error", check="metadata_yaml", path=path, message="dataset YAML 无法解析", evidence=str(exc))
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            dataset_ids[payload["id"]] = path
        for mapping in walk_mapping(payload):
            forbidden = sorted(FORBIDDEN_DATASET_KEYS.intersection(mapping.keys()))
            if forbidden:
                finding(
                    findings,
                    severity="error",
                    check="metadata_layering",
                    path=path,
                    message=f"dataset YAML 包含禁止字段: {', '.join(forbidden)}",
                )
        if isinstance(payload, dict):
            mapping_ref = payload.get("mapping_ref")
            if isinstance(mapping_ref, str) and mapping_ref:
                mapping_path = REPO / "metadata" / "mappings" / f"{mapping_ref}.yaml"
                if not mapping_path.exists():
                    finding(
                        findings,
                        severity="error",
                        check="metadata_reference",
                        path=path,
                        message=f"dataset mapping_ref 指向不存在的 mapping: {mapping_ref}",
                    )
            for dictionary_ref in payload.get("dictionary_refs") or []:
                if isinstance(dictionary_ref, str):
                    dictionary_path = REPO / "metadata" / "dictionaries" / f"{dictionary_ref}.yaml"
                    if not dictionary_path.exists():
                        finding(
                            findings,
                            severity="error",
                            check="metadata_reference",
                            path=path,
                            message=f"dataset dictionary_refs 指向不存在的 dictionary: {dictionary_ref}",
                        )

    for path in sorted((REPO / "metadata" / "mappings").glob("*.yaml")):
        try:
            payload = yaml.safe_load(read_text(path))
        except Exception as exc:  # pragma: no cover - defensive reporting.
            finding(findings, severity="error", check="metadata_yaml", path=path, message="mapping YAML 无法解析", evidence=str(exc))
            continue
        if isinstance(payload, dict):
            source_id = payload.get("source_id")
            if isinstance(source_id, str) and source_id not in dataset_ids:
                finding(
                    findings,
                    severity="error",
                    check="metadata_reference",
                    path=path,
                    message=f"mapping source_id 指向不存在的 dataset: {source_id}",
                )
            _audit_source_evidence_paths(findings, path, payload)

    for path in sorted((REPO / "metadata" / "dictionaries").glob("*.yaml")):
        try:
            payload = yaml.safe_load(read_text(path))
        except Exception as exc:  # pragma: no cover - defensive reporting.
            finding(findings, severity="error", check="metadata_yaml", path=path, message="dictionary YAML 无法解析", evidence=str(exc))
            continue
        if isinstance(payload, dict):
            _audit_source_evidence_paths(findings, path, payload)

    for path in sorted((REPO / "metadata" / "models").glob("*.yaml")):
        try:
            payload = yaml.safe_load(read_text(path))
        except Exception as exc:  # pragma: no cover - defensive reporting.
            finding(findings, severity="error", check="metadata_yaml", path=path, message="model YAML 无法解析", evidence=str(exc))
            continue
        if isinstance(payload, dict):
            for dataset_id in payload.get("datasets") or []:
                if isinstance(dataset_id, str) and dataset_id not in dataset_ids:
                    finding(
                        findings,
                        severity="error",
                        check="metadata_reference",
                        path=path,
                        message=f"model datasets 指向不存在的 dataset: {dataset_id}",
                    )

    index_dir = REPO / "metadata" / "index"
    if index_dir.exists():
        for path in sorted(index_dir.iterdir()):
            if path.name == "README.md":
                continue
            if path.suffix not in {".jsonl", ".db"}:
                finding(
                    findings,
                    severity="warning",
                    check="metadata_index",
                    path=path,
                    message="metadata/index 是生成层，应只包含预期生成文件",
                )


def _audit_source_evidence_paths(findings: list[dict[str, Any]], owner_path: Path, payload: Any) -> None:
    for mapping in walk_mapping(payload):
        source = mapping.get("source") if isinstance(mapping, dict) else None
        if not isinstance(source, str) or not source.startswith("metadata/"):
            continue
        if any(ch in source for ch in "*?[]"):
            continue
        if not (REPO / source).exists():
            finding(
                findings,
                severity="error",
                check="metadata_source_evidence",
                path=owner_path,
                message=f"source_evidence 指向不存在的文件: {source}",
            )


def audit_delivery_chain(findings: list[dict[str, Any]]) -> None:
    readme = read_text(REPO / "skills" / "README.md") if (REPO / "skills" / "README.md").exists() else ""
    for expected in EXPECTED_PIPELINE_SKILLS:
        marker = f"RA:{expected}"
        if marker not in readme:
            finding(
                findings,
                severity="warning",
                check="skill_delivery_chain",
                path="skills/README.md",
                message=f"skills/README.md 未提及核心入口或流程节点 {marker}",
            )
    report_contract = REPO / "skills" / "report" / "references" / "output-contract.md"
    if report_contract.exists() and "job_manifest" not in read_text(report_contract):
        finding(
            findings,
            severity="warning",
            check="report_contract",
            path=report_contract,
            message="report output contract 未提及 job_manifest 用户可见交付物来源",
        )


def _skill_docs(skill_name: str) -> str:
    skill_dir = REPO / "skills" / skill_name
    docs: list[str] = []
    for path in (skill_dir / "SKILL.md", skill_dir / "README.md"):
        if path.exists():
            docs.append(read_text(path))
    return "\n".join(docs)


def _token_group_found(text: str, group: list[str]) -> bool:
    return all(token in text for token in group)


def _handoff_category_status(contract: dict[str, Any], category: str, producer_docs: str, consumer_docs: str) -> dict[str, Any]:
    docs = consumer_docs if category == "consumer_inputs" else producer_docs
    if category == "state_update":
        docs = producer_docs + "\n" + consumer_docs
    groups = contract[category]
    group_statuses = [
        {
            "tokens": group,
            "found": _token_group_found(docs, group),
        }
        for group in groups
    ]
    return {
        "found": any(item["found"] for item in group_statuses),
        "token_groups": group_statuses,
    }


def build_handoff_matrix() -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for contract in HANDOFF_CONTRACTS:
        producer = contract["producer"]
        consumer = contract["consumer"]
        producer_docs = _skill_docs(producer)
        consumer_docs = _skill_docs(consumer)
        categories = {
            category: _handoff_category_status(contract, category, producer_docs, consumer_docs)
            for category in (
                "producer_outputs",
                "consumer_inputs",
                "trigger_or_next_step",
                "state_update",
            )
        }
        matrix.append(
            {
                "from": producer,
                "to": consumer,
                "producer_doc": f"skills/{producer}/SKILL.md",
                "consumer_doc": f"skills/{consumer}/SKILL.md",
                "checks": categories,
                "complete": all(item["found"] for item in categories.values()),
            }
        )
    return matrix


def _is_ignored_path(path: Path) -> bool:
    try:
        relative = path.relative_to(REPO)
    except ValueError:
        return True
    ignored_parts = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    return any(part in ignored_parts for part in relative.parts)


def build_code_inventory(skill_inventory: list[dict[str, Any]]) -> dict[str, Any]:
    python_files = sorted(
        rel(path)
        for path in REPO.glob("**/*.py")
        if path.is_file() and not _is_ignored_path(path)
    )
    shell_entrypoints = sorted(
        rel(path)
        for path in [REPO / "test.sh", REPO / "scripts" / "py"]
        if path.exists()
    )
    skill_scripts = sorted(
        script["path"]
        for skill in skill_inventory
        for script in skill.get("scripts", [])
    )
    mentioned_skill_scripts = sorted(
        script["path"]
        for skill in skill_inventory
        for script in skill.get("scripts", [])
        if script.get("mentioned_in_skill_or_readme") is True
    )
    unmentioned_skill_scripts = sorted(set(skill_scripts) - set(mentioned_skill_scripts))
    test_files = sorted(path for path in python_files if path.startswith("tests/test_"))
    runtime_files = sorted(path for path in python_files if path.startswith("runtime/"))
    project_scripts = sorted(path for path in python_files if path.startswith("scripts/"))
    skill_libs = sorted(path for path in python_files if "/lib/" in path or path.endswith("/_bootstrap.py"))
    manual_smoke_scripts = sorted(
        path
        for path in python_files
        if Path(path).name.startswith("test_") and not path.startswith("tests/")
    )
    return {
        "python_file_count": len(python_files),
        "test_file_count": len(test_files),
        "skill_script_count": len(skill_scripts),
        "runtime_file_count": len(runtime_files),
        "project_script_count": len(project_scripts),
        "python_files": python_files,
        "test_files": test_files,
        "runtime_files": runtime_files,
        "project_scripts": project_scripts,
        "skill_scripts": skill_scripts,
        "mentioned_skill_scripts": mentioned_skill_scripts,
        "potentially_internal_or_unreferenced_skill_scripts": unmentioned_skill_scripts,
        "skill_libs_and_bootstraps": skill_libs,
        "manual_smoke_scripts_outside_tests": manual_smoke_scripts,
        "shell_entrypoints": shell_entrypoints,
    }


def build_metadata_inventory() -> dict[str, Any]:
    metadata_root = REPO / "metadata"
    sync_report_files = sorted(
        rel(path)
        for path in (metadata_root / "sync").glob("**/reports/*")
        if path.is_file()
    )
    generated_index_files = sorted(
        rel(path)
        for path in (metadata_root / "index").glob("*")
        if path.is_file()
    )
    source_files = sorted(
        rel(path)
        for path in (metadata_root / "sources").glob("*")
        if path.is_file()
    )
    return {
        "datasets": sorted(rel(path) for path in (metadata_root / "datasets").glob("*.yaml")),
        "dictionaries": sorted(rel(path) for path in (metadata_root / "dictionaries").glob("*.yaml")),
        "mappings": sorted(rel(path) for path in (metadata_root / "mappings").glob("*.yaml")),
        "models": sorted(rel(path) for path in (metadata_root / "models").glob("*.yaml")),
        "sources": source_files,
        "sync_examples": sorted(
            rel(path)
            for path in (metadata_root / "sync").glob("**/*")
            if path.is_file() and path.name != "README.md"
        ),
        "sync_reports": sync_report_files,
        "generated_index": generated_index_files,
        "counts": {
            "datasets": len(list((metadata_root / "datasets").glob("*.yaml"))),
            "dictionaries": len(list((metadata_root / "dictionaries").glob("*.yaml"))),
            "mappings": len(list((metadata_root / "mappings").glob("*.yaml"))),
            "models": len(list((metadata_root / "models").glob("*.yaml"))),
            "sources": len(source_files),
            "sync_reports": len(sync_report_files),
            "generated_index": len(generated_index_files),
        },
    }


def audit_handoff_contracts(findings: list[dict[str, Any]]) -> None:
    for edge in build_handoff_matrix():
        producer_dir = REPO / "skills" / edge["from"]
        consumer_dir = REPO / "skills" / edge["to"]
        if not producer_dir.exists() or not consumer_dir.exists():
            finding(
                findings,
                severity="error",
                check="skill_handoff_contract",
                path="skills",
                message=f"核心交付链 handoff 指向不存在的 Skill: {edge['from']} -> {edge['to']}",
            )
            continue
        for category, status in edge["checks"].items():
            if status["found"]:
                continue
            finding(
                findings,
                severity="warning",
                check="skill_handoff_contract",
                path=producer_dir if category != "consumer_inputs" else consumer_dir,
                message=f"核心交付链 {edge['from']} -> {edge['to']} 缺少 {category} 契约证据",
                evidence=json.dumps(status["token_groups"], ensure_ascii=False),
            )


def build_inventory() -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    for skill_file in sorted((REPO / "skills").glob("*/SKILL.md")):
        skill_dir = skill_file.parent
        text = read_text(skill_file)
        readme = skill_dir / "README.md"
        readme_text = read_text(readme) if readme.exists() else ""
        combined_docs = text + "\n" + readme_text
        frontmatter = parse_frontmatter(text)
        script_paths = sorted(rel(path) for path in (skill_dir / "scripts").glob("**/*.py")) if (skill_dir / "scripts").exists() else []
        reference_paths = sorted(rel(path) for path in (skill_dir / "references").glob("**/*") if path.is_file()) if (skill_dir / "references").exists() else []
        skills.append(
            {
                "id": skill_dir.name,
                "declared_name": frontmatter.get("name", ""),
                "description": frontmatter.get("description", ""),
                "has_readme": readme.exists(),
                "has_input_output_section": "## 输入与输出" in readme_text,
                "has_next_step_row": "| 下一步 |" in readme_text,
                "completion_summary_count": len(re.findall(r"(?m)^## Completion Summary\b", text)),
                "script_count": len(script_paths),
                "scripts": [
                    {
                        "path": script_path,
                        "mentioned_in_skill_or_readme": Path(script_path).name in combined_docs
                        or script_path in combined_docs,
                    }
                    for script_path in script_paths
                ],
                "reference_count": len(reference_paths),
                "references": reference_paths,
                "delivery_tokens": {
                    token: token in (text + "\n" + readme_text)
                    for token in SKILL_DELIVERY_TOKENS.get(skill_dir.name, [])
                },
            }
        )

    return {
        "skills": skills,
        "metadata_files": build_metadata_inventory(),
        "code_files": build_code_inventory(skills),
        "delivery_chain": EXPECTED_PIPELINE_SKILLS,
        "handoff_matrix": build_handoff_matrix(),
    }


def run_audit() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    audit_test_layout(findings)
    audit_skills(findings)
    audit_python_collection(findings)
    audit_schemas(findings)
    audit_metadata(findings)
    audit_delivery_chain(findings)
    audit_handoff_contracts(findings)
    counts = {severity: sum(1 for item in findings if item["severity"] == severity) for severity in SEVERITY_ORDER}
    return {
        "success": counts["error"] == 0,
        "summary": {
            "skills_checked": len(list((REPO / "skills").glob("*/SKILL.md"))),
            "schemas_checked": len(list((REPO / "schemas").glob("*.json"))),
            "dataset_files_checked": len(list((REPO / "metadata" / "datasets").glob("*.yaml"))),
            "findings": counts,
        },
        "inventory": build_inventory(),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RealAnalyst project contracts.")
    parser.add_argument(
        "--fail-on",
        choices=sorted(SEVERITY_ORDER),
        default="error",
        help="Exit non-zero when findings at or above this severity exist.",
    )
    args = parser.parse_args()
    payload = run_audit()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    threshold = SEVERITY_ORDER[args.fail_on]
    should_fail = any(SEVERITY_ORDER[item["severity"]] >= threshold for item in payload["findings"])
    return 1 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

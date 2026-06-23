from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
BUILD_INDEX = REPO / "skills" / "metadata" / "scripts" / "build_index.py"
METADATA_CLI = REPO / "skills" / "metadata" / "scripts" / "metadata.py"
AUDIT_SCRIPT = REPO / "scripts" / "audit_project_contracts.py"

# metadata/index/ is a gitignored generated layer. These are the JSONL files the
# builder is expected to emit from the source YAML under metadata/{datasets,
# dictionaries,mappings}.
EXPECTED_INDEX_FILES = (
    "aliases.jsonl",
    "datasets.jsonl",
    "fields.jsonl",
    "glossary.jsonl",
    "mappings.jsonl",
    "metrics.jsonl",
)
# Current demo-fixture record total. If the demo metadata changes, update this
# value together with the source YAML so the generated layer stays auditable.
EXPECTED_TOTAL_RECORDS = 27


def _build_index(output_dir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(BUILD_INDEX), "--output-dir", str(output_dir)],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("project_contract_audit", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load audit_project_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MetadataIndexPipelineTests(unittest.TestCase):
    def test_index_build_is_deterministic_and_complete(self) -> None:
        """Two builds from the same source must be byte-identical."""
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            result_a = _build_index(Path(tmp_a))
            result_b = _build_index(Path(tmp_b))

            self.assertTrue(result_a["success"])
            self.assertEqual(result_a["total_records"], EXPECTED_TOTAL_RECORDS)
            self.assertEqual(result_b["total_records"], EXPECTED_TOTAL_RECORDS)

            for name in EXPECTED_INDEX_FILES:
                file_a = Path(tmp_a) / name
                file_b = Path(tmp_b) / name
                self.assertTrue(file_a.is_file(), f"missing generated index: {name}")
                self.assertEqual(
                    file_a.read_bytes(),
                    file_b.read_bytes(),
                    f"non-deterministic generated index: {name}",
                )

    def test_metadata_index_cli_regenerates_gitignored_layer(self) -> None:
        """`metadata.py index` rebuilds the gitignored metadata/index in place.

        The build is deterministic and idempotent, so regenerating the real
        (gitignored) layer is safe and mirrors the fresh-clone / CI fix path.
        """
        proc = subprocess.run(
            [sys.executable, str(METADATA_CLI), "index"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

        index_dir = REPO / "metadata" / "index"
        for name in EXPECTED_INDEX_FILES:
            self.assertTrue((index_dir / name).is_file(), f"index CLI did not emit {name}")

    def test_audit_counts_generated_index_after_build(self) -> None:
        """After the index exists, the project audit must count it (>= 1).

        This is the regression guard for the CI breakpoint: tests/
        test_project_contract_audit.py asserts generated_index >= 1, which only
        holds once the gitignored layer has been generated.
        """
        proc = subprocess.run(
            [sys.executable, str(METADATA_CLI), "index"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        audit = _load_audit_module()
        payload = audit.run_audit()
        generated_index = payload["inventory"]["metadata_files"]["counts"]["generated_index"]
        self.assertGreaterEqual(generated_index, 1)


if __name__ == "__main__":
    unittest.main()

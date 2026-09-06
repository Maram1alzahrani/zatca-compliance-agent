from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from evaluation.pipeline import EvaluationRunner, write_results


FINAL_SPLIT = ("final_test",)
RESULT_STEM = "phase_13_final_test"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_final_dataset_seal(data_root: Path) -> dict:
    data_root = Path(data_root)
    seal_path = data_root / "synthetic" / "v1" / "final_test_seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if seal.get("split") != "final_test" or seal.get("sealed_before_evaluation") is not True:
        raise ValueError("Final Test seal is missing its pre-evaluation declaration.")
    for name, item in seal["files"].items():
        actual = _sha256(data_root / item["path"])
        if actual != item["sha256"]:
            raise ValueError(f"Final Test sealed control file changed: {name}")
    manifest = json.loads(
        (data_root / seal["files"]["manifest"]["path"]).read_text(encoding="utf-8")
    )
    if manifest.get("split") != "final_test" or manifest.get("case_count") != len(manifest.get("cases", [])):
        raise ValueError("Final Test manifest is invalid.")
    for case in manifest["cases"]:
        if _sha256(data_root / case["invoice_file"]) != case["sha256"]:
            raise ValueError(f"Final Test invoice changed: {case['case_id']}")
    return {
        "dataset_version": seal["dataset_version"],
        "case_count": manifest["case_count"],
        "seal_file": str(seal_path),
        "seal_sha256": _sha256(seal_path),
        "control_files_verified": len(seal["files"]),
        "invoice_files_verified": len(manifest["cases"]),
    }


def build_code_freeze(project_root: Path) -> dict:
    project_root = Path(project_root).resolve()
    candidates: set[Path] = set()
    for pattern in (
        "src/**/*.py",
        "evaluation/*.py",
        "kb/rules/*",
        "kb/index/*",
        "kb/schema/*",
        "resources/ubl21/**/*.xsd",
        "requirements*.txt",
    ):
        candidates.update(path for path in project_root.glob(pattern) if path.is_file())
    for relative in (
        "scripts/run_agent.py",
        "scripts/run_correction.py",
        "scripts/run_evaluation.py",
        "scripts/run_final_evaluation.py",
        "evaluation/results/phase_12_development_validation.json",
        "data/synthetic/v1/final_test_seal.json",
    ):
        path = project_root / relative
        if path.is_file():
            candidates.add(path)
    records = [
        {
            "path": path.relative_to(project_root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(candidates)
    ]
    digest = hashlib.sha256()
    for item in records:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {
        "freeze_schema_version": "1.0.0",
        "created_before_final_inference": True,
        "file_count": len(records),
        "aggregate_sha256": digest.hexdigest(),
        "files": records,
    }


class FinalEvaluationRunner:
    """Single-use Phase 13 runner with pre-run integrity and code freezing."""

    def __init__(self, project_root: Path, *, output_dir: Path | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = self.project_root / "data"
        self.output_dir = Path(output_dir or self.project_root / "evaluation" / "results").resolve()

    def run(self) -> dict:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        state_path = self.output_dir / "phase_13_final_run_state.json"
        freeze_path = self.output_dir / "phase_13_pre_run_freeze.json"
        result_json = self.output_dir / f"{RESULT_STEM}.json"
        result_markdown = self.output_dir / f"{RESULT_STEM}.md"
        result_seal = self.output_dir / "phase_13_result_seal.json"
        protected = (state_path, freeze_path, result_json, result_markdown, result_seal)
        if any(path.exists() for path in protected):
            raise RuntimeError("Phase 13 Final Test is single-use and a run artifact already exists.")

        dataset_verification = verify_final_dataset_seal(self.data_root)
        freeze = build_code_freeze(self.project_root)
        freeze["final_dataset_verification"] = dataset_verification
        with freeze_path.open("x", encoding="utf-8") as handle:
            json.dump(freeze, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        started_at = _utc_now()
        state = {
            "run_schema_version": "1.0.0",
            "phase": 13,
            "status": "RUNNING",
            "started_at": started_at,
            "single_use": True,
        }
        with state_path.open("x", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        try:
            result = EvaluationRunner(self.data_root)._evaluate_authorized(
                FINAL_SPLIT,
                phase=13,
                final_test_accessed=True,
            )
            result["run_policy"] = {
                "single_use": True,
                "post_test_tuning_permitted": False,
                "started_at": started_at,
                "pre_run_code_aggregate_sha256": freeze["aggregate_sha256"],
                "pre_run_freeze_sha256": _sha256(freeze_path),
                "final_dataset_seal_sha256": dataset_verification["seal_sha256"],
            }
            written_json, written_markdown = write_results(
                result, self.output_dir, stem=RESULT_STEM
            )
            seal_payload = {
                "seal_schema_version": "1.0.0",
                "phase": 13,
                "single_use_final_evaluation": True,
                "files": {
                    "pre_run_freeze": {"path": freeze_path.name, "sha256": _sha256(freeze_path)},
                    "result_json": {"path": written_json.name, "sha256": _sha256(written_json)},
                    "result_markdown": {
                        "path": written_markdown.name,
                        "sha256": _sha256(written_markdown),
                    },
                },
                "pre_run_code_aggregate_sha256": freeze["aggregate_sha256"],
                "final_dataset_seal_sha256": dataset_verification["seal_sha256"],
            }
            _atomic_json(result_seal, seal_payload)
            state.update(
                {
                    "status": "COMPLETED",
                    "completed_at": _utc_now(),
                    "result_seal_sha256": _sha256(result_seal),
                }
            )
            _atomic_json(state_path, state)
            return {
                "result": result,
                "result_json": str(written_json),
                "result_markdown": str(written_markdown),
                "freeze_manifest": str(freeze_path),
                "result_seal": str(result_seal),
                "run_state": str(state_path),
            }
        except Exception as exc:
            state.update({"status": "FAILED", "failed_at": _utc_now(), "error_type": type(exc).__name__})
            _atomic_json(state_path, state)
            raise


__all__ = [
    "FINAL_SPLIT",
    "RESULT_STEM",
    "FinalEvaluationRunner",
    "build_code_freeze",
    "verify_final_dataset_seal",
]

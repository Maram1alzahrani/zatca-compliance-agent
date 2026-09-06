#!/usr/bin/env python3
"""Audit Phase 11 proposals and re-validation without touching Final Test."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ComplianceAgent, CorrectionWorkflowStatus  # noqa: E402


DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
ALLOWED_SPLITS = ("development", "validation")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> dict[str, dict]:
    return {
        row["case_id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    }


def audit(data_root: Path, splits: tuple[str, ...] = ALLOWED_SPLITS) -> dict:
    if any(split not in ALLOWED_SPLITS for split in splits):
        raise ValueError("Phase 11 correction audit permits development and validation only.")
    agent = ComplianceAgent()
    summary: dict[str, dict] = {}
    with TemporaryDirectory(prefix="zatca-phase11-") as temp_dir:
        temp_root = Path(temp_dir)
        for split in splits:
            manifest = json.loads(
                (data_root / "synthetic" / "v1" / "manifests" / f"{split}.json").read_text(encoding="utf-8")
            )
            ground_truth = _load_jsonl(data_root / "ground_truth" / "v1" / f"{split}.jsonl")
            proposal_mismatches: list[str] = []
            revalidation_failures: list[str] = []
            original_integrity_failures: list[str] = []
            eligible = 0
            applied = 0
            for case in manifest["cases"]:
                invoice_path = data_root / case["invoice_file"]
                before_hash = _sha256(invoice_path)
                analysis = agent.analyze(invoice_path, validation_date=date(2026, 9, 6))
                observed = bool(analysis.correction_proposal and analysis.correction_proposal.eligible)
                expected = bool(ground_truth[case["case_id"]]["safe_auto_correction"])
                if observed:
                    eligible += 1
                if observed != expected:
                    proposal_mismatches.append(case["case_id"])
                    continue
                if observed:
                    result = agent.correct_and_revalidate(
                        invoice_path,
                        validation_date=date(2026, 9, 6),
                        approved=True,
                        output_path=temp_root / split / f"{case['case_id']}.corrected.xml",
                    )
                    applied += 1
                    if (
                        result.status is not CorrectionWorkflowStatus.APPLIED_AND_REVALIDATED
                        or result.comparison is None
                        or not result.comparison.after_selected_checks_pass
                        or result.comparison.remaining_rule_ids
                        or result.comparison.introduced_rule_ids
                    ):
                        revalidation_failures.append(case["case_id"])
                if _sha256(invoice_path) != before_hash or before_hash != case["sha256"]:
                    original_integrity_failures.append(case["case_id"])
            summary[split] = {
                "cases": len(manifest["cases"]),
                "eligible_proposals": eligible,
                "approved_copies_applied": applied,
                "proposal_mismatches": proposal_mismatches,
                "revalidation_failures": revalidation_failures,
                "original_integrity_failures": original_integrity_failures,
                "passed": not proposal_mismatches
                and not revalidation_failures
                and not original_integrity_failures,
            }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()
    result = audit(args.data_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(item["passed"] for item in result.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

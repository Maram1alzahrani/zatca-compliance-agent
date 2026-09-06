#!/usr/bin/env python3
"""Audit development/validation labels without touching the sealed final test."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.validators import CheckStatus, validate_invoice  # noqa: E402


DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
ALLOWED_SPLITS = ("development", "validation")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def audit(data_root: Path, splits: tuple[str, ...] = ALLOWED_SPLITS) -> dict:
    if any(split not in ALLOWED_SPLITS for split in splits):
        raise ValueError("This Phase 8 audit intentionally permits development and validation only.")
    summary: dict[str, dict] = {}
    for split in splits:
        manifest = json.loads((data_root / "synthetic" / "v1" / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
        truth = {record["case_id"]: record for record in read_jsonl(data_root / "ground_truth" / "v1" / f"{split}.jsonl")}
        mismatches = []
        for case in manifest["cases"]:
            report = validate_invoice(
                data_root / case["invoice_file"],
                validation_date=date(2026, 9, 6),
            )
            predicted = [check.rule_id for check in report.checks if check.status is CheckStatus.FAIL]
            expected = truth[case["case_id"]]["expected_rule_ids"]
            if predicted != expected:
                mismatches.append({"case_id": case["case_id"], "expected": expected, "predicted": predicted})
        summary[split] = {"cases": len(manifest["cases"]), "mismatches": mismatches, "passed": not mismatches}
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

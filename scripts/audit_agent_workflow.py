#!/usr/bin/env python3
"""Audit analysis tool orchestration on development/validation only."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ComplianceAgent  # noqa: E402
from src.tools import ToolCallStatus  # noqa: E402
from src.validators import CheckStatus  # noqa: E402


DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
ALLOWED_SPLITS = ("development", "validation")


def audit(data_root: Path, splits: tuple[str, ...] = ALLOWED_SPLITS) -> dict:
    if any(split not in ALLOWED_SPLITS for split in splits):
        raise ValueError("Agent audit permits development and validation only.")
    agent = ComplianceAgent()
    summary = {}
    for split in splits:
        manifest = json.loads(
            (data_root / "synthetic" / "v1" / "manifests" / f"{split}.json").read_text(encoding="utf-8")
        )
        failures = []
        tool_calls = 0
        for case in manifest["cases"]:
            result = agent.analyze(data_root / case["invoice_file"], validation_date=date(2026, 9, 6))
            failed_rules = [check.rule_id for check in result.checks if check.status is CheckStatus.FAIL]
            retrieved_rules = [
                event.input_summary["rule_id"]
                for event in result.tool_trace
                if event.tool_name == "retrieve_zatca_rule"
            ]
            # Failure path: validate + exact evidence retrievals + explain + correction proposal.
            expected_tools = 1 + len(failed_rules) + (2 if failed_rules else 0)
            valid = (
                failed_rules == retrieved_rules
                and failed_rules == [issue.rule_id for issue in result.issues]
                and len(result.tool_trace) == expected_tools
                and all(event.status is ToolCallStatus.SUCCESS for event in result.tool_trace)
                and all(issue.evidence_status == "VERIFIED" for issue in result.issues)
                and ((result.correction_proposal is not None) == bool(failed_rules))
            )
            if not valid:
                failures.append(case["case_id"])
            tool_calls += len(result.tool_trace)
        summary[split] = {
            "cases": len(manifest["cases"]),
            "tool_calls": tool_calls,
            "workflow_failures": failures,
            "passed": not failures,
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

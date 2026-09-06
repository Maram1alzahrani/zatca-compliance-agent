#!/usr/bin/env python3
"""Propose, optionally approve, apply-to-copy, and re-validate a correction."""

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 11 conservative correction workflow.")
    parser.add_argument("invoice", type=Path)
    parser.add_argument("--validation-date", type=date.fromisoformat, required=True)
    parser.add_argument("--approve", action="store_true", help="Explicitly approve writing the proposed correction.")
    parser.add_argument("--output", type=Path, help="New corrected XML path; required with --approve.")
    args = parser.parse_args()
    if args.approve and args.output is None:
        parser.error("--output is required with --approve")
    if not args.approve and args.output is not None:
        parser.error("--output is only accepted with --approve")
    result = ComplianceAgent().correct_and_revalidate(
        args.invoice,
        validation_date=args.validation_date,
        approved=args.approve,
        output_path=args.output,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

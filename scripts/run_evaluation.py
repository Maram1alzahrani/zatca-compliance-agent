#!/usr/bin/env python3
"""Run Phase 12 evaluation on Development and Validation only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.pipeline import EvaluationRunner, write_results  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the ZATCA POC without opening Final Test.")
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "evaluation" / "results")
    parser.add_argument(
        "--splits",
        nargs="+",
        choices=("development", "validation"),
        default=["development", "validation"],
    )
    args = parser.parse_args()
    result = EvaluationRunner(args.data_root).evaluate(tuple(args.splits))
    json_path, markdown_path = write_results(result, args.output_dir)
    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
                "aggregate": result["aggregate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Execute the single permitted Phase 13 Final Test run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.final_evaluation import FinalEvaluationRunner  # noqa: E402


def main() -> None:
    outcome = FinalEvaluationRunner(PROJECT_ROOT).run()
    aggregate = outcome["result"]["aggregate"]
    print(
        json.dumps(
            {
                "status": "COMPLETED",
                "result_json": outcome["result_json"],
                "result_markdown": outcome["result_markdown"],
                "freeze_manifest": outcome["freeze_manifest"],
                "result_seal": outcome["result_seal"],
                "case_count": aggregate["case_count"],
                "detection_f1": aggregate["error_detection"]["micro"]["f1"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

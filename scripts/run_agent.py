#!/usr/bin/env python3
"""Run validation, evidence retrieval, grounded explanation, and correction proposal."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ComplianceAgent, OpenAIExplanationProvider  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the grounded compliance analysis and proposal workflow.")
    parser.add_argument("invoice", type=Path)
    parser.add_argument("--validation-date", type=date.fromisoformat, required=True)
    parser.add_argument("--llm", action="store_true", help="Use the optional OpenAI structured narrative adapter.")
    parser.add_argument("--model", help="Explicit OpenAI model name; required with --llm.")
    parser.add_argument("--language", choices=("ar", "en"), default="ar")
    args = parser.parse_args()
    if args.llm and not args.model:
        parser.error("--model is required when --llm is enabled")
    provider = OpenAIExplanationProvider(args.model, args.language) if args.llm else None
    result = ComplianceAgent(explanation_provider=provider).analyze(
        args.invoice,
        validation_date=args.validation_date,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

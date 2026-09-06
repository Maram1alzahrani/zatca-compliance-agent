#!/usr/bin/env python3
"""Query the verified ZATCA POC evidence corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag import VerifiedRuleRetriever  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve verified evidence; performs no invoice validation.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rule-id")
    group.add_argument("--query")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    retriever = VerifiedRuleRetriever()
    response = retriever.retrieve_rule(args.rule_id) if args.rule_id else retriever.search(args.query, args.top_k)
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

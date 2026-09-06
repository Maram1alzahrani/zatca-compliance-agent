#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.validators import validate_invoice


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the eight deterministic POC checks.")
    parser.add_argument("invoice", type=Path)
    parser.add_argument("--validation-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    report = validate_invoice(args.invoice, validation_date=args.validation_date)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

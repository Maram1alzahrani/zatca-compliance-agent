from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from evaluation.sdk_oracle import run_sdk_oracle, write_benchmark_result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare independently sourced invoice fixtures against the local ZATCA SDK and this POC."
    )
    parser.add_argument(
        "invoice_dir",
        type=Path,
        help="Directory containing independently sourced XML invoice fixtures.",
    )
    parser.add_argument(
        "--sdk-command",
        required=True,
        help=(
            "Command template used to run the installed SDK. It must contain exactly one "
            "{invoice} placeholder, e.g. 'fatoora ... {invoice}'."
        ),
    )
    parser.add_argument(
        "--validation-date",
        required=True,
        type=date.fromisoformat,
        help="Injected validation date in YYYY-MM-DD format for deterministic date checks.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/external_sdk_benchmark.json"),
    )
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    invoices = sorted(path for path in args.invoice_dir.glob("*.xml") if path.is_file())
    if not invoices:
        raise SystemExit(f"No .xml files found in {args.invoice_dir}")

    results = []
    for invoice in invoices:
        result = run_sdk_oracle(
            invoice,
            command_template=args.sdk_command,
            validation_date=args.validation_date,
            timeout_seconds=args.timeout_seconds,
        )
        results.append(result)
        status = "AGREE" if result.agreement else "DISAGREE"
        print(
            f"{status}: {invoice.name} | SDK={result.sdk_status} | "
            f"POC={'PASSED' if result.poc_selected_checks_pass else 'FAILED'}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_benchmark_result(args.output, results)
    print(f"Wrote benchmark result: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

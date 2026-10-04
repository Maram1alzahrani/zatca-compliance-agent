"""Adapter for comparing selected POC checks with an external ZATCA SDK result.

This module does not package, download, or redistribute the SDK. The caller supplies
an installed SDK command template and invoice fixtures obtained independently from
this repository.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from src.validators import CheckStatus, validate_invoice


_GLOBAL_RESULT = re.compile(
    r"GLOBAL\s+VALIDATION\s+RESULT\s*-\s*(PASSED|FAILED)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SdkOracleResult:
    invoice: str
    sdk_status: str
    poc_selected_checks_pass: bool
    agreement: bool
    failed_rule_ids: tuple[str, ...]
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict:
        return {
            "invoice": self.invoice,
            "sdk_status": self.sdk_status,
            "poc_selected_checks_pass": self.poc_selected_checks_pass,
            "agreement": self.agreement,
            "failed_rule_ids": list(self.failed_rule_ids),
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def parse_sdk_global_result(output: str) -> str:
    """Return PASSED/FAILED from ZATCA SDK console output."""
    matches = _GLOBAL_RESULT.findall(output)
    if not matches:
        raise ValueError("SDK output did not contain a GLOBAL VALIDATION RESULT.")
    normalized = {value.upper() for value in matches}
    if len(normalized) != 1:
        raise ValueError("SDK output contained conflicting global validation results.")
    return next(iter(normalized))


def build_sdk_command(command_template: str, invoice_path: Path) -> tuple[str, ...]:
    """Build a safe argv list from a template containing exactly one {invoice} token."""
    if command_template.count("{invoice}") != 1:
        raise ValueError("SDK command template must contain exactly one {invoice} placeholder.")
    rendered = command_template.replace("{invoice}", str(Path(invoice_path).resolve()))
    return tuple(shlex.split(rendered))


def run_sdk_oracle(
    invoice_path: Path,
    *,
    command_template: str,
    validation_date: date,
    timeout_seconds: int = 60,
) -> SdkOracleResult:
    invoice_path = Path(invoice_path).resolve()
    command = build_sdk_command(command_template, invoice_path)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    sdk_status = parse_sdk_global_result(combined)

    report = validate_invoice(invoice_path, validation_date=validation_date)
    failed_rule_ids = tuple(
        check.rule_id for check in report.checks if check.status is CheckStatus.FAIL
    )
    sdk_pass = sdk_status == "PASSED"
    return SdkOracleResult(
        invoice=str(invoice_path),
        sdk_status=sdk_status,
        poc_selected_checks_pass=report.selected_checks_pass,
        agreement=sdk_pass == report.selected_checks_pass,
        failed_rule_ids=failed_rule_ids,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def summarize(results: Iterable[SdkOracleResult]) -> dict:
    items = list(results)
    agreements = sum(item.agreement for item in items)
    sdk_pass = sum(item.sdk_status == "PASSED" for item in items)
    poc_pass = sum(item.poc_selected_checks_pass for item in items)
    return {
        "cases": len(items),
        "agreements": agreements,
        "agreement_rate": agreements / len(items) if items else 0.0,
        "sdk_pass": sdk_pass,
        "sdk_fail": len(items) - sdk_pass,
        "poc_pass": poc_pass,
        "poc_fail": len(items) - poc_pass,
        "disagreements": [
            {
                "invoice": item.invoice,
                "sdk_status": item.sdk_status,
                "poc_selected_checks_pass": item.poc_selected_checks_pass,
                "failed_rule_ids": list(item.failed_rule_ids),
            }
            for item in items
            if not item.agreement
        ],
    }


def write_benchmark_result(path: Path, results: Iterable[SdkOracleResult]) -> None:
    items = list(results)
    payload = {
        "schema_version": "1.0.0",
        "oracle": "ZATCA SDK local execution",
        "interpretation": (
            "Agreement compares the SDK global validation result with whether this POC "
            "passes its selected checks. Disagreement does not by itself identify which "
            "system is wrong because the POC intentionally covers only a subset of ZATCA rules."
        ),
        "summary": summarize(items),
        "cases": [item.to_dict() for item in items],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "SdkOracleResult",
    "build_sdk_command",
    "parse_sdk_global_result",
    "run_sdk_oracle",
    "summarize",
    "write_benchmark_result",
]

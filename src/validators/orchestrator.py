from __future__ import annotations

from datetime import date
from pathlib import Path

from src.parsers import parse_invoice
from src.validators.checks import (
    RULE_IDS,
    not_run,
    validate_buyer,
    validate_invoice_id,
    validate_invoice_type,
    validate_issue_date,
    validate_lines,
    validate_seller,
    validate_vat_and_totals,
    validate_xml,
)
from src.validators.result import CheckStatus, ValidationReport


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XSD = ROOT / "resources" / "ubl21" / "xsd" / "maindoc" / "UBL-Invoice-2.1.xsd"


def validate_invoice(
    invoice_path: Path,
    *,
    validation_date: date,
    xsd_path: Path = DEFAULT_XSD,
) -> ValidationReport:
    outcome = parse_invoice(invoice_path)
    xml_result = validate_xml(outcome.document, outcome.error, xsd_path)
    if outcome.invoice is None:
        checks = (xml_result,) + tuple(
            not_run(rule_id, "Canonical parsing failed; dependent check was not run.")
            for rule_id in RULE_IDS[1:]
        )
        return ValidationReport(str(invoice_path), None, False, checks)

    invoice = outcome.invoice
    checks = (
        xml_result,
        validate_invoice_id(invoice),
        validate_issue_date(invoice, validation_date),
        validate_invoice_type(invoice),
        validate_seller(invoice),
        validate_buyer(invoice),
        validate_lines(invoice),
        validate_vat_and_totals(invoice),
    )
    selected_checks_pass = all(check.status is CheckStatus.PASS for check in checks)
    return ValidationReport(str(invoice_path), invoice.invoice_number, selected_checks_pass, checks)


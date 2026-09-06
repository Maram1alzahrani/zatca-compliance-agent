from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from lxml import etree

from src.models import CanonicalInvoice
from src.validators.result import CheckResult, CheckStatus


RULE_IDS = (
    "MVP-XML-001",
    "MVP-ID-001",
    "MVP-DATE-001",
    "MVP-TYPE-001",
    "MVP-SELLER-001",
    "MVP-BUYER-001",
    "MVP-LINE-001",
    "MVP-VAT-TOTAL-001",
)


def passed(rule_id: str, message: str) -> CheckResult:
    return CheckResult(rule_id, CheckStatus.PASS, message)


def failed(rule_id: str, message: str, details: list[str] | tuple[str, ...]) -> CheckResult:
    return CheckResult(rule_id, CheckStatus.FAIL, message, tuple(details))


def not_run(rule_id: str, reason: str) -> CheckResult:
    return CheckResult(rule_id, CheckStatus.NOT_RUN, reason)


def validate_xml(document: etree._ElementTree | None, parse_error: str | None, xsd_path: Path) -> CheckResult:
    rule_id = "MVP-XML-001"
    if document is None:
        return failed(rule_id, "XML could not be parsed.", [parse_error or "Unknown parse error"])
    try:
        schema = etree.XMLSchema(etree.parse(str(xsd_path)))
    except (etree.XMLSchemaParseError, etree.XMLSyntaxError, OSError) as exc:
        return not_run(rule_id, f"Trusted UBL XSD unavailable: {exc}")
    if schema.validate(document):
        return passed(rule_id, "XML is well formed and valid against UBL Invoice 2.1 XSD.")
    return failed(
        rule_id,
        "XML is well formed but does not satisfy UBL Invoice 2.1 XSD.",
        [str(error) for error in schema.error_log],
    )


def validate_invoice_id(invoice: CanonicalInvoice) -> CheckResult:
    if invoice.invoice_number and invoice.invoice_number.strip():
        return passed("MVP-ID-001", "Invoice number is present.")
    return failed("MVP-ID-001", "Invoice number is missing or empty.", ["BT-1 / BR-02"])


def validate_issue_date(invoice: CanonicalInvoice, validation_date: date) -> CheckResult:
    value = invoice.issue_date
    problems = []
    parsed = None
    if not value:
        problems.append("Issue date is missing.")
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        problems.append("Issue date must use YYYY-MM-DD.")
    else:
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            problems.append("Issue date is not a real Gregorian calendar date.")
    if parsed and parsed > validation_date:
        problems.append(f"Issue date {parsed} is after validation date {validation_date}.")
    if problems:
        return failed("MVP-DATE-001", "Invoice issue date failed selected checks.", problems)
    return passed("MVP-DATE-001", "Invoice issue date is present, valid, and not in the future.")


def validate_invoice_type(invoice: CanonicalInvoice) -> CheckResult:
    problems = []
    if invoice.invoice_type_code != "388":
        problems.append(f"Expected type code 388; found {invoice.invoice_type_code!r}.")
    if invoice.transaction_code != "0100000":
        problems.append(f"Expected frozen transaction code 0100000; found {invoice.transaction_code!r}.")
    if problems:
        return failed("MVP-TYPE-001", "Invoice is outside the frozen Standard Tax Invoice profile.", problems)
    return passed("MVP-TYPE-001", "Invoice type code and Saudi transaction code match the frozen profile.")


def validate_seller(invoice: CanonicalInvoice) -> CheckResult:
    problems = []
    if not invoice.seller or not invoice.seller.name or not invoice.seller.name.strip():
        problems.append("Seller name is missing or empty.")
    vat = invoice.seller.vat_number if invoice.seller else None
    if not vat:
        problems.append("Seller VAT number is missing or empty.")
    elif not re.fullmatch(r"3\d{13}3", vat):
        problems.append("Seller VAT number must contain 15 digits and start/end with 3.")
    if problems:
        return failed("MVP-SELLER-001", "Seller data failed selected checks.", problems)
    return passed("MVP-SELLER-001", "Seller name and VAT-number format passed selected checks.")


def validate_buyer(invoice: CanonicalInvoice) -> CheckResult:
    if invoice.buyer and invoice.buyer.name and invoice.buyer.name.strip():
        return passed("MVP-BUYER-001", "Buyer name is present for the Tax Invoice profile.")
    return failed("MVP-BUYER-001", "Buyer name is missing or empty for a Tax Invoice.", ["BT-44 / BR-KSA-42"])


def _decimal(value: str | None, field: str, problems: list[str], default: Decimal | None = None) -> Decimal | None:
    if value is None:
        if default is not None:
            return default
        problems.append(f"{field} is missing.")
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        problems.append(f"{field} is not a valid decimal: {value!r}.")
        return None
    if not parsed.is_finite():
        problems.append(f"{field} must be a finite decimal: {value!r}.")
        return None
    return parsed


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_lines(invoice: CanonicalInvoice) -> CheckResult:
    problems: list[str] = []
    if not invoice.lines:
        return failed("MVP-LINE-001", "No invoice lines were found.", ["BG-25"])
    declared_lines: list[Decimal] = []
    for index, line in enumerate(invoice.lines, start=1):
        quantity = _decimal(line.quantity, f"line {index} quantity", problems)
        price = _decimal(line.net_price, f"line {index} net price", problems)
        base = _decimal(line.price_base_quantity, f"line {index} base quantity", problems, Decimal("1"))
        allowance = _decimal(line.allowance_amount, f"line {index} allowance", problems, Decimal("0"))
        charge = _decimal(line.charge_amount, f"line {index} charge", problems, Decimal("0"))
        declared = _decimal(line.net_amount, f"line {index} net amount", problems)
        if declared is not None:
            declared_lines.append(declared)
        if None in (quantity, price, base, allowance, charge, declared):
            continue
        if base == 0:
            problems.append(f"line {index} base quantity is zero.")
            continue
        try:
            expected = _round((price / base) * quantity) - allowance + charge
            expected = _round(expected)
        except DecimalException:
            problems.append(f"line {index} arithmetic exceeds supported decimal bounds.")
            continue
        if declared != expected:
            problems.append(f"line {index} net amount {declared} != expected {expected}.")
    totals = invoice.totals
    document_sum = _decimal(totals.line_extension_amount if totals else None, "BT-106 line-extension total", problems)
    if document_sum is not None and declared_lines:
        try:
            expected_sum = _round(sum(declared_lines, Decimal("0")))
        except DecimalException:
            problems.append("BT-106 reconciliation exceeds supported decimal bounds.")
            expected_sum = None
        if expected_sum is not None and document_sum != expected_sum:
            problems.append(f"BT-106 {document_sum} != sum of BT-131 values {expected_sum}.")
    if problems:
        return failed("MVP-LINE-001", "Invoice line calculations failed selected checks.", problems)
    return passed("MVP-LINE-001", "Line net amounts and the document line sum reconcile.")


def validate_vat_and_totals(invoice: CanonicalInvoice) -> CheckResult:
    problems: list[str] = []
    if not invoice.vat_breakdowns:
        return failed("MVP-VAT-TOTAL-001", "VAT breakdown is missing.", ["BG-23 / BR-CO-18"])
    line_net_by_standard = Decimal("0")
    for index, line in enumerate(invoice.lines, start=1):
        if line.vat_category_code == "S":
            value = _decimal(line.net_amount, f"line {index} net amount", problems)
            if value is not None:
                try:
                    line_net_by_standard += value
                except DecimalException:
                    problems.append("Standard line-net aggregation exceeds supported decimal bounds.")

    breakdown_tax_sum = Decimal("0")
    for index, breakdown in enumerate(invoice.vat_breakdowns, start=1):
        taxable = _decimal(breakdown.taxable_amount, f"breakdown {index} taxable amount", problems)
        rate = _decimal(breakdown.rate, f"breakdown {index} rate", problems)
        tax = _decimal(breakdown.tax_amount, f"breakdown {index} tax amount", problems)
        if breakdown.category_code != "S":
            problems.append(f"breakdown {index} category {breakdown.category_code!r} is outside frozen S profile.")
        try:
            rounded_line_net = _round(line_net_by_standard)
        except DecimalException:
            rounded_line_net = None
        if taxable is not None and rounded_line_net is not None and taxable != rounded_line_net:
            problems.append(f"breakdown {index} taxable amount {taxable} != standard line net sum {rounded_line_net}.")
        if None not in (taxable, rate, tax):
            try:
                expected_tax = _round(taxable * rate / Decimal("100"))
                if tax != expected_tax:
                    problems.append(f"breakdown {index} tax amount {tax} != expected {expected_tax}.")
                breakdown_tax_sum += tax
            except DecimalException:
                problems.append(f"breakdown {index} arithmetic exceeds supported decimal bounds.")

    totals = invoice.totals
    if totals is None:
        problems.append("Legal monetary totals are missing.")
    else:
        line_total = _decimal(totals.line_extension_amount, "BT-106", problems)
        allowance = _decimal(totals.allowance_total_amount, "BT-107", problems, Decimal("0"))
        charge = _decimal(totals.charge_total_amount, "BT-108", problems, Decimal("0"))
        exclusive = _decimal(totals.tax_exclusive_amount, "BT-109", problems)
        total_tax = _decimal(totals.tax_amount, "BT-110", problems)
        inclusive = _decimal(totals.tax_inclusive_amount, "BT-112", problems)
        if None not in (line_total, allowance, charge, exclusive):
            try:
                expected_exclusive = _round(line_total - allowance + charge)
                if exclusive != expected_exclusive:
                    problems.append(f"BT-109 {exclusive} != expected {expected_exclusive}.")
            except DecimalException:
                problems.append("BT-109 arithmetic exceeds supported decimal bounds.")
        try:
            rounded_tax_sum = _round(breakdown_tax_sum)
        except DecimalException:
            rounded_tax_sum = None
            problems.append("BT-110 aggregation exceeds supported decimal bounds.")
        if total_tax is not None and rounded_tax_sum is not None and total_tax != rounded_tax_sum:
            problems.append(f"BT-110 {total_tax} != VAT breakdown sum {rounded_tax_sum}.")
        if None not in (exclusive, total_tax, inclusive):
            try:
                expected_inclusive = _round(exclusive + total_tax)
                if inclusive != expected_inclusive:
                    problems.append(f"BT-112 {inclusive} != BT-109 + BT-110 ({expected_inclusive}).")
            except DecimalException:
                problems.append("BT-112 arithmetic exceeds supported decimal bounds.")
    if problems:
        return failed("MVP-VAT-TOTAL-001", "VAT or document totals failed selected checks.", problems)
    return passed("MVP-VAT-TOTAL-001", "Standard VAT breakdown and document totals reconcile.")

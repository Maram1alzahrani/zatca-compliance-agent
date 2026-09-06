from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from lxml import etree

from src.models import InvoiceParty
from src.validators.checks import (
    _round,
    validate_buyer,
    validate_invoice_id,
    validate_invoice_type,
    validate_issue_date,
    validate_lines,
    validate_seller,
    validate_vat_and_totals,
    validate_xml,
)
from src.validators.result import CheckStatus
from tests.invoice_factory import standard_breakdown, standard_invoice, standard_line, standard_totals


VALIDATION_DATE = date(2026, 9, 6)
ROOT = Path(__file__).resolve().parents[1]
BASELINE_XML = ROOT / "data" / "synthetic" / "dev" / "invoices" / "inv_0001.xml"
XSD = ROOT / "resources" / "ubl21" / "xsd" / "maindoc" / "UBL-Invoice-2.1.xsd"


class FieldValidatorTests(unittest.TestCase):
    def test_invoice_id_accepts_non_empty_value(self) -> None:
        self.assertIs(validate_invoice_id(standard_invoice()).status, CheckStatus.PASS)

    def test_invoice_id_rejects_missing_empty_and_whitespace(self) -> None:
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertIs(validate_invoice_id(standard_invoice(invoice_number=value)).status, CheckStatus.FAIL)

    def test_issue_date_accepts_past_and_validation_day(self) -> None:
        for value in ("2026-09-01", "2026-09-06"):
            with self.subTest(value=value):
                self.assertIs(validate_issue_date(standard_invoice(issue_date=value), VALIDATION_DATE).status, CheckStatus.PASS)

    def test_issue_date_rejects_missing_format_calendar_and_future_errors(self) -> None:
        for value in (None, "01/09/2026", "2026-02-30", "2026-09-07"):
            with self.subTest(value=value):
                self.assertIs(validate_issue_date(standard_invoice(issue_date=value), VALIDATION_DATE).status, CheckStatus.FAIL)

    def test_invoice_type_requires_both_frozen_codes(self) -> None:
        cases = (("388", "0100000", CheckStatus.PASS), ("999", "0100000", CheckStatus.FAIL), ("388", None, CheckStatus.FAIL))
        for type_code, transaction_code, expected in cases:
            with self.subTest(type_code=type_code, transaction_code=transaction_code):
                result = validate_invoice_type(standard_invoice(invoice_type_code=type_code, transaction_code=transaction_code))
                self.assertIs(result.status, expected)

    def test_seller_accepts_selected_vat_format(self) -> None:
        self.assertIs(validate_seller(standard_invoice()).status, CheckStatus.PASS)

    def test_seller_rejects_missing_or_blank_name(self) -> None:
        for seller in (None, InvoiceParty(None, "310000000000003"), InvoiceParty("  ", "310000000000003")):
            with self.subTest(seller=seller):
                self.assertIs(validate_seller(standard_invoice(seller=seller)).status, CheckStatus.FAIL)

    def test_seller_rejects_invalid_vat_shapes(self) -> None:
        for vat in (None, "", "210000000000003", "310000000000002", "31000000000003", "3ABCDEFGHIJKLM3"):
            with self.subTest(vat=vat):
                result = validate_seller(standard_invoice(seller=InvoiceParty("Seller", vat)))
                self.assertIs(result.status, CheckStatus.FAIL)

    def test_buyer_requires_non_blank_name(self) -> None:
        self.assertIs(validate_buyer(standard_invoice()).status, CheckStatus.PASS)
        for buyer in (None, InvoiceParty(None), InvoiceParty("   ")):
            with self.subTest(buyer=buyer):
                self.assertIs(validate_buyer(standard_invoice(buyer=buyer)).status, CheckStatus.FAIL)


class LineValidatorTests(unittest.TestCase):
    def test_valid_line_passes(self) -> None:
        self.assertIs(validate_lines(standard_invoice()).status, CheckStatus.PASS)

    def test_half_up_rounding_is_explicit(self) -> None:
        self.assertEqual(Decimal("1.01"), _round(Decimal("1.005")))
        line = standard_line(quantity="1", net_price="1.005", net_amount="1.01")
        totals = standard_totals(line_extension_amount="1.01")
        self.assertIs(validate_lines(standard_invoice(lines=(line,), totals=totals)).status, CheckStatus.PASS)

    def test_base_quantity_allowance_and_charge_formula(self) -> None:
        line = standard_line(
            quantity="2", net_price="100.00", price_base_quantity="2",
            allowance_amount="5.00", charge_amount="2.00", net_amount="97.00",
        )
        totals = standard_totals(line_extension_amount="97.00")
        self.assertIs(validate_lines(standard_invoice(lines=(line,), totals=totals)).status, CheckStatus.PASS)

    def test_multiple_lines_reconcile_to_bt_106(self) -> None:
        lines = (standard_line(), standard_line(line_id="2", quantity="1", net_price="40", net_amount="40.00"))
        totals = standard_totals(line_extension_amount="140.00")
        self.assertIs(validate_lines(standard_invoice(lines=lines, totals=totals)).status, CheckStatus.PASS)

    def test_no_lines_fails(self) -> None:
        self.assertIs(validate_lines(standard_invoice(lines=())).status, CheckStatus.FAIL)

    def test_zero_base_quantity_fails_without_crashing(self) -> None:
        result = validate_lines(standard_invoice(lines=(standard_line(price_base_quantity="0"),)))
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertTrue(any("base quantity is zero" in detail for detail in result.details))

    def test_missing_or_invalid_operand_fails(self) -> None:
        for value in (None, "abc", "NaN", "Infinity", "-Infinity", "1E+999999"):
            with self.subTest(value=value):
                line = standard_line(net_price=value)
                self.assertIs(validate_lines(standard_invoice(lines=(line,))).status, CheckStatus.FAIL)

    def test_line_amount_mismatch_fails(self) -> None:
        result = validate_lines(standard_invoice(lines=(standard_line(net_amount="99.99"),)))
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertTrue(any("net amount" in detail and "expected" in detail for detail in result.details))

    def test_bt_106_mismatch_fails(self) -> None:
        result = validate_lines(standard_invoice(totals=standard_totals(line_extension_amount="90.00")))
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertTrue(any("BT-106" in detail for detail in result.details))


class VatAndTotalsValidatorTests(unittest.TestCase):
    def test_valid_vat_and_totals_pass(self) -> None:
        self.assertIs(validate_vat_and_totals(standard_invoice()).status, CheckStatus.PASS)

    def test_missing_breakdown_fails(self) -> None:
        self.assertIs(validate_vat_and_totals(standard_invoice(vat_breakdowns=())).status, CheckStatus.FAIL)

    def test_vat_uses_half_up_rounding(self) -> None:
        line = standard_line(quantity="1", net_price="0.10", net_amount="0.10")
        breakdown = standard_breakdown(taxable_amount="0.10", tax_amount="0.02")
        totals = standard_totals(line_extension_amount="0.10", tax_exclusive_amount="0.10", tax_amount="0.02", tax_inclusive_amount="0.12")
        result = validate_vat_and_totals(standard_invoice(lines=(line,), vat_breakdowns=(breakdown,), totals=totals))
        self.assertIs(result.status, CheckStatus.PASS)

    def test_breakdown_taxable_amount_must_match_standard_lines(self) -> None:
        result = validate_vat_and_totals(standard_invoice(vat_breakdowns=(standard_breakdown(taxable_amount="90.00"),)))
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertTrue(any("taxable amount" in detail for detail in result.details))

    def test_breakdown_tax_amount_must_match_rate(self) -> None:
        result = validate_vat_and_totals(standard_invoice(vat_breakdowns=(standard_breakdown(tax_amount="14.99"),)))
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertTrue(any("expected" in detail for detail in result.details))

    def test_non_standard_category_fails_frozen_profile(self) -> None:
        result = validate_vat_and_totals(standard_invoice(vat_breakdowns=(standard_breakdown(category_code="Z"),)))
        self.assertIs(result.status, CheckStatus.FAIL)

    def test_missing_totals_fails(self) -> None:
        invoice = standard_invoice()
        invoice = type(invoice)(
            invoice_number=invoice.invoice_number,
            issue_date=invoice.issue_date,
            invoice_type_code=invoice.invoice_type_code,
            transaction_code=invoice.transaction_code,
            seller=invoice.seller,
            buyer=invoice.buyer,
            lines=invoice.lines,
            vat_breakdowns=invoice.vat_breakdowns,
            totals=None,
        )
        self.assertIs(validate_vat_and_totals(invoice).status, CheckStatus.FAIL)

    def test_bt_109_includes_document_allowance_and_charge(self) -> None:
        totals = standard_totals(
            line_extension_amount="100.00", allowance_total_amount="5.00",
            charge_total_amount="2.00", tax_exclusive_amount="97.00",
            tax_amount="15.00", tax_inclusive_amount="112.00",
        )
        self.assertIs(validate_vat_and_totals(standard_invoice(totals=totals)).status, CheckStatus.PASS)

    def test_each_document_total_equation_can_fail(self) -> None:
        cases = (
            standard_totals(tax_exclusive_amount="99.00", tax_inclusive_amount="114.00"),
            standard_totals(tax_amount="14.00", tax_inclusive_amount="114.00"),
            standard_totals(tax_inclusive_amount="114.00"),
        )
        for totals in cases:
            with self.subTest(totals=totals):
                self.assertIs(validate_vat_and_totals(standard_invoice(totals=totals)).status, CheckStatus.FAIL)

    def test_invalid_and_non_finite_money_fail_without_crashing(self) -> None:
        for value in ("abc", "NaN", "Infinity", "-Infinity", "1E+999999"):
            with self.subTest(value=value):
                totals = standard_totals(tax_amount=value)
                self.assertIs(validate_vat_and_totals(standard_invoice(totals=totals)).status, CheckStatus.FAIL)


class XmlValidatorTests(unittest.TestCase):
    def test_official_ubl_xsd_accepts_baseline(self) -> None:
        document = etree.parse(str(BASELINE_XML))
        self.assertIs(validate_xml(document, None, XSD).status, CheckStatus.PASS)

    def test_unparseable_document_fails(self) -> None:
        result = validate_xml(None, "synthetic parse error", XSD)
        self.assertIs(result.status, CheckStatus.FAIL)
        self.assertIn("synthetic parse error", result.details)

    def test_missing_trusted_xsd_is_not_run(self) -> None:
        document = etree.parse(str(BASELINE_XML))
        result = validate_xml(document, None, Path("missing-schema.xsd"))
        self.assertIs(result.status, CheckStatus.NOT_RUN)

    def test_well_formed_but_xsd_invalid_document_fails(self) -> None:
        document = etree.parse(str(ROOT / "data" / "synthetic" / "dev" / "invoices" / "inv_0003.xml"))
        self.assertIs(validate_xml(document, None, XSD).status, CheckStatus.FAIL)


if __name__ == "__main__":
    unittest.main()

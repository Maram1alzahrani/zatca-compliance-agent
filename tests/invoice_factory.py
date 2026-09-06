"""Canonical invoice fixtures shared by deterministic-validator unit tests."""

from __future__ import annotations

from src.models import CanonicalInvoice, InvoiceLine, InvoiceParty, InvoiceTotals, VatBreakdown


def standard_line(
    *,
    line_id: str = "1",
    quantity: str | None = "2",
    net_price: str | None = "50.00",
    price_base_quantity: str | None = "1",
    allowance_amount: str | None = "0.00",
    charge_amount: str | None = "0.00",
    net_amount: str | None = "100.00",
    vat_category_code: str | None = "S",
) -> InvoiceLine:
    return InvoiceLine(
        line_id=line_id,
        quantity=quantity,
        unit_code="PCE",
        item_name="Synthetic item",
        net_price=net_price,
        price_base_quantity=price_base_quantity,
        allowance_amount=allowance_amount,
        charge_amount=charge_amount,
        net_amount=net_amount,
        vat_category_code=vat_category_code,
        vat_rate="15.00",
    )


def standard_breakdown(
    *,
    category_code: str | None = "S",
    rate: str | None = "15.00",
    taxable_amount: str | None = "100.00",
    tax_amount: str | None = "15.00",
) -> VatBreakdown:
    return VatBreakdown(
        category_code=category_code,
        rate=rate,
        taxable_amount=taxable_amount,
        tax_amount=tax_amount,
    )


def standard_totals(
    *,
    line_extension_amount: str | None = "100.00",
    allowance_total_amount: str | None = "0.00",
    charge_total_amount: str | None = "0.00",
    tax_exclusive_amount: str | None = "100.00",
    tax_amount: str | None = "15.00",
    tax_inclusive_amount: str | None = "115.00",
) -> InvoiceTotals:
    return InvoiceTotals(
        line_extension_amount=line_extension_amount,
        allowance_total_amount=allowance_total_amount,
        charge_total_amount=charge_total_amount,
        tax_exclusive_amount=tax_exclusive_amount,
        tax_amount=tax_amount,
        tax_inclusive_amount=tax_inclusive_amount,
        prepaid_amount="0.00",
        payable_amount=tax_inclusive_amount,
    )


def standard_invoice(
    *,
    invoice_number: str | None = "SYN-UNIT-001",
    issue_date: str | None = "2026-09-01",
    invoice_type_code: str | None = "388",
    transaction_code: str | None = "0100000",
    seller: InvoiceParty | None = InvoiceParty("Synthetic Seller LLC", "310000000000003"),
    buyer: InvoiceParty | None = InvoiceParty("Synthetic Buyer LLC", "310000000000013"),
    lines: tuple[InvoiceLine, ...] | None = None,
    vat_breakdowns: tuple[VatBreakdown, ...] | None = None,
    totals: InvoiceTotals | None = None,
) -> CanonicalInvoice:
    return CanonicalInvoice(
        invoice_number=invoice_number,
        issue_date=issue_date,
        invoice_type_code=invoice_type_code,
        transaction_code=transaction_code,
        document_currency_code="SAR",
        tax_currency_code="SAR",
        seller=seller,
        buyer=buyer,
        lines=(standard_line(),) if lines is None else lines,
        vat_breakdowns=(standard_breakdown(),) if vat_breakdowns is None else vat_breakdowns,
        totals=standard_totals() if totals is None else totals,
    )

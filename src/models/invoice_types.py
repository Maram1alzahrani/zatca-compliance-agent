"""Typed canonical representation used between parsing and validation.

These dataclasses preserve invoice values. They deliberately do not enforce
ZATCA business rules: an invalid or incomplete invoice must remain
representable so deterministic validators can report the correct finding.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DecimalText = str


@dataclass(frozen=True, slots=True)
class InvoiceParty:
    name: str | None = None
    vat_number: str | None = None


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    line_id: str | None = None
    quantity: DecimalText | None = None
    unit_code: str | None = None
    item_name: str | None = None
    net_price: DecimalText | None = None
    price_base_quantity: DecimalText | None = None
    allowance_amount: DecimalText | None = None
    charge_amount: DecimalText | None = None
    net_amount: DecimalText | None = None
    vat_category_code: str | None = None
    vat_rate: DecimalText | None = None
    vat_amount: DecimalText | None = None
    amount_with_vat: DecimalText | None = None


@dataclass(frozen=True, slots=True)
class VatBreakdown:
    category_code: str | None = None
    rate: DecimalText | None = None
    taxable_amount: DecimalText | None = None
    tax_amount: DecimalText | None = None


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    line_extension_amount: DecimalText | None = None
    allowance_total_amount: DecimalText | None = None
    charge_total_amount: DecimalText | None = None
    tax_exclusive_amount: DecimalText | None = None
    tax_amount: DecimalText | None = None
    tax_inclusive_amount: DecimalText | None = None
    prepaid_amount: DecimalText | None = None
    payable_rounding_amount: DecimalText | None = None
    payable_amount: DecimalText | None = None


@dataclass(frozen=True, slots=True)
class CanonicalInvoice:
    schema_version: str = "1.0.0"
    invoice_number: str | None = None
    uuid: str | None = None
    issue_date: str | None = None
    issue_time: str | None = None
    invoice_type_code: str | None = None
    transaction_code: str | None = None
    document_currency_code: str | None = None
    tax_currency_code: str | None = None
    seller: InvoiceParty | None = None
    buyer: InvoiceParty | None = None
    lines: tuple[InvoiceLine, ...] = field(default_factory=tuple)
    vat_breakdowns: tuple[VatBreakdown, ...] = field(default_factory=tuple)
    totals: InvoiceTotals | None = None


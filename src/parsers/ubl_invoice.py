"""Securely parse UBL Invoice XML into the compliance-neutral canonical model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from src.models import CanonicalInvoice, InvoiceLine, InvoiceParty, InvoiceTotals, VatBreakdown


NS = {
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    invoice: CanonicalInvoice | None
    document: etree._ElementTree | None
    error: str | None


def _text(node: etree._Element, path: str) -> str | None:
    values = node.xpath(path, namespaces=NS)
    if not values:
        return None
    value = values[0]
    if isinstance(value, etree._Element):
        value = value.text
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _sum_optional(node: etree._Element, path: str) -> str | None:
    values = [str(value).strip() for value in node.xpath(path, namespaces=NS)]
    values = [value for value in values if value]
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    # Multiple allowances/charges are outside the frozen profile. Preserve a
    # parseable marker instead of silently combining business values.
    return "MULTIPLE:" + "|".join(values)


def parse_invoice(path: Path) -> ParseOutcome:
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        huge_tree=False,
        remove_comments=False,
    )
    try:
        document = etree.parse(str(path), parser)
    except (etree.XMLSyntaxError, OSError) as exc:
        return ParseOutcome(None, None, str(exc))

    root = document.getroot()
    if root.tag != f"{{{NS['ubl']}}}Invoice":
        return ParseOutcome(None, document, "Root element is not UBL Invoice-2")

    seller = InvoiceParty(
        name=_text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName"),
        vat_number=_text(root, "cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme[cac:TaxScheme/cbc:ID='VAT']/cbc:CompanyID"),
    )
    buyer = InvoiceParty(
        name=_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName"),
        vat_number=_text(root, "cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme[cac:TaxScheme/cbc:ID='VAT']/cbc:CompanyID"),
    )
    lines = []
    for line in root.xpath("cac:InvoiceLine", namespaces=NS):
        lines.append(
            InvoiceLine(
                line_id=_text(line, "cbc:ID"),
                quantity=_text(line, "cbc:InvoicedQuantity"),
                unit_code=_text(line, "cbc:InvoicedQuantity/@unitCode"),
                item_name=_text(line, "cac:Item/cbc:Name"),
                net_price=_text(line, "cac:Price/cbc:PriceAmount"),
                price_base_quantity=_text(line, "cac:Price/cbc:BaseQuantity"),
                allowance_amount=_sum_optional(line, "cac:AllowanceCharge[cbc:ChargeIndicator='false']/cbc:Amount/text()"),
                charge_amount=_sum_optional(line, "cac:AllowanceCharge[cbc:ChargeIndicator='true']/cbc:Amount/text()"),
                net_amount=_text(line, "cbc:LineExtensionAmount"),
                vat_category_code=_text(line, "cac:Item/cac:ClassifiedTaxCategory/cbc:ID"),
                vat_rate=_text(line, "cac:Item/cac:ClassifiedTaxCategory/cbc:Percent"),
                vat_amount=_text(line, "cac:TaxTotal/cbc:TaxAmount"),
                amount_with_vat=_text(line, "cac:TaxTotal/cbc:RoundingAmount"),
            )
        )
    breakdowns = []
    for subtotal in root.xpath("cac:TaxTotal/cac:TaxSubtotal", namespaces=NS):
        breakdowns.append(
            VatBreakdown(
                category_code=_text(subtotal, "cac:TaxCategory/cbc:ID"),
                rate=_text(subtotal, "cac:TaxCategory/cbc:Percent"),
                taxable_amount=_text(subtotal, "cbc:TaxableAmount"),
                tax_amount=_text(subtotal, "cbc:TaxAmount"),
            )
        )
    totals_node = root.find("cac:LegalMonetaryTotal", namespaces=NS)
    totals = None
    if totals_node is not None:
        totals = InvoiceTotals(
            line_extension_amount=_text(totals_node, "cbc:LineExtensionAmount"),
            allowance_total_amount=_text(totals_node, "cbc:AllowanceTotalAmount"),
            charge_total_amount=_text(totals_node, "cbc:ChargeTotalAmount"),
            tax_exclusive_amount=_text(totals_node, "cbc:TaxExclusiveAmount"),
            tax_amount=_text(root, "cac:TaxTotal[not(cac:TaxSubtotal)]/cbc:TaxAmount"),
            tax_inclusive_amount=_text(totals_node, "cbc:TaxInclusiveAmount"),
            prepaid_amount=_text(totals_node, "cbc:PrepaidAmount"),
            payable_rounding_amount=_text(totals_node, "cbc:PayableRoundingAmount"),
            payable_amount=_text(totals_node, "cbc:PayableAmount"),
        )

    invoice_type_nodes = root.xpath("cbc:InvoiceTypeCode", namespaces=NS)
    transaction_code = invoice_type_nodes[0].get("name") if invoice_type_nodes else None
    invoice = CanonicalInvoice(
        invoice_number=_text(root, "cbc:ID"),
        uuid=_text(root, "cbc:UUID"),
        issue_date=_text(root, "cbc:IssueDate"),
        issue_time=_text(root, "cbc:IssueTime"),
        invoice_type_code=_text(root, "cbc:InvoiceTypeCode"),
        transaction_code=transaction_code,
        document_currency_code=_text(root, "cbc:DocumentCurrencyCode"),
        tax_currency_code=_text(root, "cbc:TaxCurrencyCode"),
        seller=seller,
        buyer=buyer,
        lines=tuple(lines),
        vat_breakdowns=tuple(breakdowns),
        totals=totals,
    )
    return ParseOutcome(invoice, document, None)


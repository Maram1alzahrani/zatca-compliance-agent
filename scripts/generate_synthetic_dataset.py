#!/usr/bin/env python3
"""Generate the small, deterministic Phase 5 synthetic development dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import uuid
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = ROOT / "data"
GENERATOR_VERSION = "0.1.0"
SEED = 20260906
VALIDATION_DATE = "2026-09-06"

NS = {
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
ET.register_namespace("", NS["ubl"])
ET.register_namespace("cac", NS["cac"])
ET.register_namespace("cbc", NS["cbc"])


def q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def child(parent: ET.Element, prefix: str, local: str, text: str | None = None, **attrs: str) -> ET.Element:
    element = ET.SubElement(parent, q(prefix, local), attrs)
    element.text = text
    return element


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def make_party(parent: ET.Element, role: str, name: str, vat: str, crn: str) -> None:
    wrapper = child(parent, "cac", role)
    party = child(wrapper, "cac", "Party")
    identification = child(party, "cac", "PartyIdentification")
    child(identification, "cbc", "ID", crn, schemeID="CRN")
    address = child(party, "cac", "PostalAddress")
    child(address, "cbc", "StreetName", "Synthetic Street")
    child(address, "cbc", "BuildingNumber", "1234")
    child(address, "cbc", "CitySubdivisionName", "Synthetic District")
    child(address, "cbc", "CityName", "Jeddah")
    child(address, "cbc", "PostalZone", "23456")
    child(address, "cbc", "CountrySubentity", "Makkah Region")
    country = child(address, "cac", "Country")
    child(country, "cbc", "IdentificationCode", "SA")
    tax_scheme = child(party, "cac", "PartyTaxScheme")
    child(tax_scheme, "cbc", "CompanyID", vat)
    scheme = child(tax_scheme, "cac", "TaxScheme")
    child(scheme, "cbc", "ID", "VAT")
    legal = child(party, "cac", "PartyLegalEntity")
    child(legal, "cbc", "RegistrationName", name)


def add_tax_total(parent: ET.Element, taxable: Decimal, vat: Decimal, with_subtotal: bool) -> None:
    total = child(parent, "cac", "TaxTotal")
    child(total, "cbc", "TaxAmount", money(vat), currencyID="SAR")
    if with_subtotal:
        subtotal = child(total, "cac", "TaxSubtotal")
        child(subtotal, "cbc", "TaxableAmount", money(taxable), currencyID="SAR")
        child(subtotal, "cbc", "TaxAmount", money(vat), currencyID="SAR")
        category = child(subtotal, "cac", "TaxCategory")
        child(category, "cbc", "ID", "S")
        child(category, "cbc", "Percent", "15.00")
        scheme = child(category, "cac", "TaxScheme")
        child(scheme, "cbc", "ID", "VAT")


def add_line(root: ET.Element, line_id: str, quantity: Decimal, price: Decimal, item_name: str) -> None:
    net = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat = (net * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    line = child(root, "cac", "InvoiceLine")
    child(line, "cbc", "ID", line_id)
    child(line, "cbc", "InvoicedQuantity", str(quantity), unitCode="PCE")
    child(line, "cbc", "LineExtensionAmount", money(net), currencyID="SAR")
    tax_total = child(line, "cac", "TaxTotal")
    child(tax_total, "cbc", "TaxAmount", money(vat), currencyID="SAR")
    child(tax_total, "cbc", "RoundingAmount", money(net + vat), currencyID="SAR")
    item = child(line, "cac", "Item")
    child(item, "cbc", "Name", item_name)
    category = child(item, "cac", "ClassifiedTaxCategory")
    child(category, "cbc", "ID", "S")
    child(category, "cbc", "Percent", "15.00")
    scheme = child(category, "cac", "TaxScheme")
    child(scheme, "cbc", "ID", "VAT")
    price_node = child(line, "cac", "Price")
    child(price_node, "cbc", "PriceAmount", money(price), currencyID="SAR")
    child(price_node, "cbc", "BaseQuantity", "1", unitCode="PCE")


def build_baseline(sequence: int) -> ET.Element:
    root = ET.Element(q("ubl", "Invoice"))
    child(root, "cbc", "ProfileID", "reporting:1.0")
    child(root, "cbc", "ID", f"SYN-{20260000 + sequence}")
    child(root, "cbc", "UUID", str(uuid.uuid5(uuid.NAMESPACE_URL, f"zatca-poc-{SEED}-{sequence}")))
    child(root, "cbc", "IssueDate", "2026-09-01")
    child(root, "cbc", "IssueTime", "12:00:00")
    child(root, "cbc", "InvoiceTypeCode", "388", name="0100000")
    child(root, "cbc", "DocumentCurrencyCode", "SAR")
    child(root, "cbc", "TaxCurrencyCode", "SAR")
    make_party(root, "AccountingSupplierParty", "Synthetic Seller LLC", "310000000000003", "1010000001")
    make_party(root, "AccountingCustomerParty", "Synthetic Buyer LLC", "310000000000013", "1010000002")
    total_net = Decimal("140.00")
    total_vat = Decimal("21.00")
    add_tax_total(root, total_net, total_vat, with_subtotal=True)
    add_tax_total(root, total_net, total_vat, with_subtotal=False)
    legal = child(root, "cac", "LegalMonetaryTotal")
    child(legal, "cbc", "LineExtensionAmount", "140.00", currencyID="SAR")
    child(legal, "cbc", "TaxExclusiveAmount", "140.00", currencyID="SAR")
    child(legal, "cbc", "TaxInclusiveAmount", "161.00", currencyID="SAR")
    child(legal, "cbc", "AllowanceTotalAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "ChargeTotalAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "PrepaidAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "PayableAmount", "161.00", currencyID="SAR")
    add_line(root, "1", Decimal("2"), Decimal("50.00"), "Synthetic Item Alpha")
    add_line(root, "2", Decimal("1"), Decimal("40.00"), "Synthetic Item Beta")
    return root


def find(root: ET.Element, path: str) -> ET.Element:
    node = root.find(path, NS)
    if node is None:
        raise RuntimeError(f"Generator path not found: {path}")
    return node


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    rule_ids: tuple[str, ...]
    error_type: str
    operator: str | None
    target: str | None
    before: str | None
    after: str | None
    expected_value: str | None
    auto_correctable: bool
    mutate: Callable[[ET.Element], None] | None = None
    malformed_xml: bool = False


def remove_path(path: str) -> Callable[[ET.Element], None]:
    def mutate(root: ET.Element) -> None:
        parts = path.split("/")
        parent = root if len(parts) == 1 else find(root, "/".join(parts[:-1]))
        node = find(root, path)
        parent.remove(node)
    return mutate


def set_text(path: str, value: str) -> Callable[[ET.Element], None]:
    def mutate(root: ET.Element) -> None:
        find(root, path).text = value
    return mutate


CASES = (
    CaseSpec("C0001", (), "COMPLIANT", None, None, None, None, None, False),
    CaseSpec("C0002", ("MVP-XML-001",), "XML_ERROR", "truncate_closing_tag", "raw_xml", "</Invoice>", None, "well-formed XML", False, malformed_xml=True),
    CaseSpec("C0003", ("MVP-XML-001", "MVP-ID-001"), "MISSING_FIELD", "remove_element", "invoice_number", "SYN-20260003", None, "SYN-20260003", False, mutate=remove_path("cbc:ID")),
    CaseSpec("C0004", ("MVP-XML-001", "MVP-DATE-001"), "INVALID_FORMAT", "replace_text", "issue_date", "2026-09-01", "01/09/2026", "2026-09-01", False, mutate=set_text("cbc:IssueDate", "01/09/2026")),
    CaseSpec("C0005", ("MVP-TYPE-001",), "INVALID_VALUE", "replace_text", "invoice_type_code", "388", "999", "388", False, mutate=set_text("cbc:InvoiceTypeCode", "999")),
    CaseSpec("C0006", ("MVP-SELLER-001",), "MISSING_FIELD", "remove_element", "seller.name", "Synthetic Seller LLC", None, "Synthetic Seller LLC", False, mutate=remove_path("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")),
    CaseSpec("C0007", ("MVP-SELLER-001",), "INVALID_FORMAT", "replace_text", "seller.vat_number", "310000000000003", "110000000000002", "310000000000003", False, mutate=set_text("cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID", "110000000000002")),
    CaseSpec("C0008", ("MVP-BUYER-001",), "MISSING_FIELD", "remove_element", "buyer.name", "Synthetic Buyer LLC", None, "Synthetic Buyer LLC", False, mutate=remove_path("cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName")),
    CaseSpec("C0009", ("MVP-LINE-001", "MVP-VAT-TOTAL-001"), "CALCULATION_ERROR", "replace_text", "lines[0].net_amount", "100.00", "90.00", "100.00", True, mutate=set_text("cac:InvoiceLine/cbc:LineExtensionAmount", "90.00")),
    CaseSpec("C0010", ("MVP-LINE-001", "MVP-VAT-TOTAL-001"), "TOTAL_MISMATCH", "replace_text", "totals.line_extension_amount", "140.00", "130.00", "140.00", True, mutate=set_text("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", "130.00")),
    CaseSpec("C0011", ("MVP-VAT-TOTAL-001",), "VAT_ERROR", "replace_text", "vat_breakdowns[0].tax_amount", "21.00", "20.00", "21.00", True, mutate=set_text("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "20.00")),
    CaseSpec("C0012", ("MVP-VAT-TOTAL-001",), "TOTAL_MISMATCH", "replace_text", "totals.tax_inclusive_amount", "161.00", "160.00", "161.00", True, mutate=set_text("cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "160.00")),
)


def serialize(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def json_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"


def generate(data_root: Path) -> None:
    synthetic = data_root / "synthetic"
    invoice_dir = synthetic / "dev" / "invoices"
    metadata_dir = synthetic / "metadata"
    injection_dir = synthetic / "error_injections"
    manifest_dir = synthetic / "manifests"
    ground_truth_dir = data_root / "ground_truth"

    if invoice_dir.exists():
        shutil.rmtree(invoice_dir)
    for directory in (invoice_dir, metadata_dir, injection_dir, manifest_dir, ground_truth_dir):
        directory.mkdir(parents=True, exist_ok=True)

    metadata_records = []
    truth_records = []
    injection_records = []
    manifest_cases = []

    for sequence, spec in enumerate(CASES, start=1):
        root = build_baseline(sequence)
        if spec.mutate:
            spec.mutate(root)
        payload = serialize(root)
        if spec.malformed_xml:
            closing = b"</Invoice>"
            if closing not in payload:
                raise RuntimeError("Expected Invoice closing tag was not found")
            payload = payload.replace(closing, b"", 1)

        filename = f"inv_{sequence:04d}.xml"
        relative_invoice = f"synthetic/dev/invoices/{filename}"
        (invoice_dir / filename).write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()

        metadata_records.append({
            "case_id": spec.case_id,
            "split": "development",
            "invoice_file": relative_invoice,
            "synthetic": True,
            "contains_real_entity_data": False,
            "profile": "standard_tax_invoice_base",
            "generator_version": GENERATOR_VERSION,
            "seed": SEED,
            "validation_date": VALIDATION_DATE,
        })
        truth_records.append({
            "case_id": spec.case_id,
            "expected_selected_checks_pass": not spec.rule_ids,
            "expected_rule_ids": list(spec.rule_ids),
            "expected_issue_count": len(spec.rule_ids),
            "primary_error_type": spec.error_type,
            "target_field": spec.target,
            "expected_corrected_value": spec.expected_value,
            "safe_auto_correction": spec.auto_correctable,
        })
        injection_records.append({
            "case_id": spec.case_id,
            "injection_applied": spec.operator is not None,
            "operator": spec.operator,
            "target_field": spec.target,
            "before": spec.before,
            "after": spec.after,
            "seed": SEED,
        })
        manifest_cases.append({
            "case_id": spec.case_id,
            "invoice_file": relative_invoice,
            "sha256": digest,
        })

    (metadata_dir / "dev.jsonl").write_text("".join(map(json_line, metadata_records)), encoding="utf-8")
    (ground_truth_dir / "dev.jsonl").write_text("".join(map(json_line, truth_records)), encoding="utf-8")
    (injection_dir / "dev.jsonl").write_text("".join(map(json_line, injection_records)), encoding="utf-8")
    manifest = {
        "dataset_version": "0.1.0",
        "split": "development",
        "case_count": len(CASES),
        "generator_version": GENERATOR_VERSION,
        "seed": SEED,
        "cases": manifest_cases,
    }
    (manifest_dir / "dev_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()
    generate(args.data_root)
    print(f"Generated {len(CASES)} development cases under {args.data_root}")


if __name__ == "__main__":
    main()

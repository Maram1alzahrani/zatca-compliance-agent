#!/usr/bin/env python3
"""Generate the deterministic, split-isolated synthetic dataset v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_synthetic_dataset import (  # noqa: E402
    NS,
    add_line,
    add_tax_total,
    child,
    find,
    make_party,
    money,
    q,
    serialize,
)


DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
VALIDATION_DATE = date(2026, 9, 6)
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
RULE_ORDER = (
    "MVP-XML-001",
    "MVP-ID-001",
    "MVP-DATE-001",
    "MVP-TYPE-001",
    "MVP-SELLER-001",
    "MVP-BUYER-001",
    "MVP-LINE-001",
    "MVP-VAT-TOTAL-001",
)
SPLITS = {
    "development": {"count": 48, "seed": 2026090611, "compliant": 8},
    "validation": {"count": 32, "seed": 2026090622, "compliant": 5},
    "final_test": {"count": 32, "seed": 2026090633, "compliant": 5},
}

SELLER_NAMES = (
    "Synthetic Horizon Trading LLC",
    "Synthetic Cedar Services LLC",
    "Synthetic Dune Supplies LLC",
    "Synthetic Beacon Technology LLC",
)
BUYER_NAMES = (
    "Synthetic Pearl Markets LLC",
    "Synthetic Valley Retail LLC",
    "Synthetic Palm Projects LLC",
    "Synthetic Coast Operations LLC",
)
ITEM_NAMES = (
    "Synthetic Office Item",
    "Synthetic Service Package",
    "Synthetic Equipment Unit",
    "Synthetic Maintenance Item",
    "Synthetic Training Unit",
)
README_TEXT = """# Synthetic Dataset v1

This dataset contains fully synthetic UBL 2.1 invoices for the selected ZATCA educational POC checks.

## Split policy

| Split | Cases | Permitted use before Phase 13 |
|---|---:|---|
| Development | 48 | Validator and pipeline development |
| Validation | 32 | Design verification and tuning checks |
| Final Test | 32 | No validator, prompt, RAG, or agent tuning |

Invoice XML, metadata, error-injection records, and ground truth are stored separately. Invoice filenames and XML payloads do not contain labels. All companies, identifiers, items, and monetary values are synthetic.

The Final Test control files are hashed in `final_test_seal.json`. The Phase 8 audit script accepts only Development and Validation. Final Test evaluation is intentionally deferred to Phase 13.

Passing this dataset's selected checks does not imply ZATCA approval, certification, clearance, reporting, or full compliance.
"""


def json_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def synthetic_vat(split_seed: int, index: int, party_offset: int) -> str:
    middle = (split_seed + index * 97 + party_offset) % (10**13)
    return f"3{middle:013d}3"


def build_varied_invoice(split: str, split_seed: int, index: int, rng: random.Random) -> ET.Element:
    root = ET.Element(q("ubl", "Invoice"))
    child(root, "cbc", "ProfileID", "reporting:1.0")
    child(root, "cbc", "ID", f"SYNV1-{split_seed}-{index:04d}")
    child(root, "cbc", "UUID", str(uuid.uuid5(uuid.NAMESPACE_URL, f"zatca-v1-{split}-{split_seed}-{index}")))
    issue_date = VALIDATION_DATE - timedelta(days=rng.randint(0, 120))
    child(root, "cbc", "IssueDate", issue_date.isoformat())
    child(root, "cbc", "IssueTime", f"{rng.randint(8, 17):02d}:{rng.choice((0, 15, 30, 45)):02d}:00")
    child(root, "cbc", "InvoiceTypeCode", "388", name="0100000")
    child(root, "cbc", "DocumentCurrencyCode", "SAR")
    child(root, "cbc", "TaxCurrencyCode", "SAR")
    make_party(
        root,
        "AccountingSupplierParty",
        SELLER_NAMES[rng.randrange(len(SELLER_NAMES))],
        synthetic_vat(split_seed, index, 11),
        f"10{(split_seed + index) % 100000000:08d}",
    )
    make_party(
        root,
        "AccountingCustomerParty",
        BUYER_NAMES[rng.randrange(len(BUYER_NAMES))],
        synthetic_vat(split_seed, index, 29),
        f"20{(split_seed + index) % 100000000:08d}",
    )

    line_specs: list[tuple[Decimal, Decimal, str]] = []
    for _ in range(rng.randint(1, 3)):
        quantity = Decimal(rng.randint(1, 5))
        price = (Decimal(rng.randint(500, 25000)) / Decimal("100")).quantize(Decimal("0.01"))
        line_specs.append((quantity, price, ITEM_NAMES[rng.randrange(len(ITEM_NAMES))]))
    total_net = sum((quantity * price for quantity, price, _ in line_specs), Decimal("0")).quantize(Decimal("0.01"))
    total_vat = (total_net * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    add_tax_total(root, total_net, total_vat, with_subtotal=True)
    add_tax_total(root, total_net, total_vat, with_subtotal=False)
    legal = child(root, "cac", "LegalMonetaryTotal")
    child(legal, "cbc", "LineExtensionAmount", money(total_net), currencyID="SAR")
    child(legal, "cbc", "TaxExclusiveAmount", money(total_net), currencyID="SAR")
    child(legal, "cbc", "TaxInclusiveAmount", money(total_net + total_vat), currencyID="SAR")
    child(legal, "cbc", "AllowanceTotalAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "ChargeTotalAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "PrepaidAmount", "0.00", currencyID="SAR")
    child(legal, "cbc", "PayableAmount", money(total_net + total_vat), currencyID="SAR")
    for line_index, (quantity, price, name) in enumerate(line_specs, start=1):
        add_line(root, str(line_index), quantity, price, name)
    return root


Mutation = Callable[[ET.Element], dict]


@dataclass(frozen=True)
class Operator:
    name: str
    rule_ids: tuple[str, ...]
    error_type: str
    safe_auto_correction: bool
    mutate: Mutation | None
    malformed_after_serialization: bool = False


def remove_element(path: str, target: str) -> Mutation:
    def mutate(root: ET.Element) -> dict:
        parts = path.split("/")
        parent = root if len(parts) == 1 else find(root, "/".join(parts[:-1]))
        node = find(root, path)
        before = node.text
        parent.remove(node)
        return {"target_field": target, "before": before, "after": None, "expected_value": before}
    return mutate


def replace_text(path: str, value: str, target: str) -> Mutation:
    def mutate(root: ET.Element) -> dict:
        node = find(root, path)
        before = node.text
        node.text = value
        return {"target_field": target, "before": before, "after": value, "expected_value": before}
    return mutate


def subtract_money(path: str, target: str) -> Mutation:
    def mutate(root: ET.Element) -> dict:
        node = find(root, path)
        before = node.text or "0.00"
        after = money(Decimal(before) - Decimal("1.00"))
        node.text = after
        return {"target_field": target, "before": before, "after": after, "expected_value": before}
    return mutate


def set_future_date(root: ET.Element) -> dict:
    node = find(root, "cbc:IssueDate")
    before = node.text
    after = (VALIDATION_DATE + timedelta(days=1)).isoformat()
    node.text = after
    return {"target_field": "issue_date", "before": before, "after": after, "expected_value": before}


def set_transaction_code(root: ET.Element) -> dict:
    node = find(root, "cbc:InvoiceTypeCode")
    before = node.get("name")
    node.set("name", "0200000")
    return {"target_field": "transaction_code", "before": before, "after": "0200000", "expected_value": "0100000"}


OPERATORS = {
    "malformed_xml": Operator("malformed_xml", ("MVP-XML-001",), "XML_ERROR", False, None, True),
    "missing_invoice_id": Operator("missing_invoice_id", ("MVP-XML-001", "MVP-ID-001"), "MISSING_FIELD", False, remove_element("cbc:ID", "invoice_number")),
    "invalid_date_format": Operator("invalid_date_format", ("MVP-XML-001", "MVP-DATE-001"), "INVALID_FORMAT", False, replace_text("cbc:IssueDate", "06/09/2026", "issue_date")),
    "future_date": Operator("future_date", ("MVP-DATE-001",), "INVALID_VALUE", False, set_future_date),
    "invalid_invoice_type": Operator("invalid_invoice_type", ("MVP-TYPE-001",), "INVALID_VALUE", False, replace_text("cbc:InvoiceTypeCode", "999", "invoice_type_code")),
    "invalid_transaction_code": Operator("invalid_transaction_code", ("MVP-TYPE-001",), "INVALID_VALUE", False, set_transaction_code),
    "missing_seller_name": Operator("missing_seller_name", ("MVP-SELLER-001",), "MISSING_FIELD", False, remove_element("cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", "seller.name")),
    "invalid_seller_vat": Operator("invalid_seller_vat", ("MVP-SELLER-001",), "INVALID_FORMAT", False, replace_text("cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:CompanyID", "110000000000002", "seller.vat_number")),
    "missing_buyer_name": Operator("missing_buyer_name", ("MVP-BUYER-001",), "MISSING_FIELD", False, remove_element("cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName", "buyer.name")),
    "line_net_mismatch": Operator("line_net_mismatch", ("MVP-LINE-001", "MVP-VAT-TOTAL-001"), "CALCULATION_ERROR", True, subtract_money("cac:InvoiceLine/cbc:LineExtensionAmount", "lines[0].net_amount")),
    "bt106_mismatch": Operator("bt106_mismatch", ("MVP-LINE-001", "MVP-VAT-TOTAL-001"), "TOTAL_MISMATCH", True, subtract_money("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", "totals.line_extension_amount")),
    "vat_tax_mismatch": Operator("vat_tax_mismatch", ("MVP-VAT-TOTAL-001",), "VAT_ERROR", True, subtract_money("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", "vat_breakdowns[0].tax_amount")),
    "vat_taxable_mismatch": Operator("vat_taxable_mismatch", ("MVP-VAT-TOTAL-001",), "VAT_ERROR", True, subtract_money("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount", "vat_breakdowns[0].taxable_amount")),
    "inclusive_total_mismatch": Operator("inclusive_total_mismatch", ("MVP-VAT-TOTAL-001",), "TOTAL_MISMATCH", True, subtract_money("cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", "totals.tax_inclusive_amount")),
    "invalid_line_price_decimal": Operator("invalid_line_price_decimal", ("MVP-XML-001", "MVP-LINE-001"), "INVALID_FORMAT", False, replace_text("cac:InvoiceLine/cac:Price/cbc:PriceAmount", "not-a-decimal", "lines[0].net_price")),
}

SINGLES = tuple(OPERATORS)
COMBINATIONS = (
    ("missing_invoice_id", "invalid_seller_vat"),
    ("future_date", "invalid_invoice_type"),
    ("missing_seller_name", "missing_buyer_name"),
    ("line_net_mismatch", "vat_tax_mismatch"),
    ("bt106_mismatch", "inclusive_total_mismatch"),
    ("invalid_transaction_code", "vat_taxable_mismatch"),
    ("invalid_date_format", "missing_buyer_name"),
    ("invalid_line_price_decimal", "invalid_seller_vat"),
    ("missing_invoice_id", "line_net_mismatch"),
    ("future_date", "missing_seller_name", "inclusive_total_mismatch"),
    ("invalid_invoice_type", "missing_buyer_name", "vat_tax_mismatch"),
    ("invalid_seller_vat", "bt106_mismatch"),
)


def schedule_for(split: str, rng: random.Random) -> list[tuple[str, ...]]:
    settings = SPLITS[split]
    schedule: list[tuple[str, ...]] = [()] * settings["compliant"]
    schedule.extend((name,) for name in SINGLES)
    combination_index = {"development": 0, "validation": 2, "final_test": 5}[split]
    while len(schedule) < settings["count"]:
        schedule.append(COMBINATIONS[combination_index % len(COMBINATIONS)])
        combination_index += 1
    rng.shuffle(schedule)
    return schedule


def ordered_rules(operator_names: tuple[str, ...]) -> list[str]:
    present = {rule for name in operator_names for rule in OPERATORS[name].rule_ids}
    return [rule for rule in RULE_ORDER if rule in present]


def generate(data_root: Path) -> None:
    dataset_root = data_root / "synthetic" / "v1"
    truth_root = data_root / "ground_truth" / "v1"
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    if truth_root.exists():
        shutil.rmtree(truth_root)
    (dataset_root / "metadata").mkdir(parents=True, exist_ok=True)
    (dataset_root / "error_injections").mkdir(parents=True, exist_ok=True)
    (dataset_root / "manifests").mkdir(parents=True, exist_ok=True)
    truth_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "README.md").write_text(README_TEXT, encoding="utf-8")

    for split, settings in SPLITS.items():
        rng = random.Random(settings["seed"])
        schedule = schedule_for(split, rng)
        invoice_dir = dataset_root / split / "invoices"
        invoice_dir.mkdir(parents=True, exist_ok=True)
        metadata_records: list[dict] = []
        truth_records: list[dict] = []
        injection_records: list[dict] = []
        manifest_cases: list[dict] = []

        for index, operator_names in enumerate(schedule, start=1):
            case_rng = random.Random(settings["seed"] + index * 1009)
            root = build_varied_invoice(split, settings["seed"], index, case_rng)
            injection_details = []
            malformed = False
            for name in operator_names:
                operator = OPERATORS[name]
                if operator.malformed_after_serialization:
                    malformed = True
                    detail = {"target_field": "raw_xml", "before": "complete document", "after": "truncated closing tag", "expected_value": "well-formed XML"}
                else:
                    assert operator.mutate is not None
                    detail = operator.mutate(root)
                injection_details.append({
                    "operator": name,
                    "error_type": operator.error_type,
                    "rule_ids": list(operator.rule_ids),
                    "safe_auto_correction": operator.safe_auto_correction,
                    **detail,
                })
            payload = serialize(root)
            if malformed:
                payload = payload.replace(b"</Invoice>", b"", 1)

            filename = f"invoice_{index:04d}.xml"
            relative_invoice = f"synthetic/v1/{split}/invoices/{filename}"
            (invoice_dir / filename).write_bytes(payload)
            case_id = uuid.uuid5(uuid.NAMESPACE_URL, f"zatca-v1-case-{split}-{index}").hex[:16]
            expected_rules = ordered_rules(operator_names)
            manifest_cases.append({"case_id": case_id, "invoice_file": relative_invoice, "sha256": sha256_bytes(payload)})
            metadata_records.append({
                "case_id": case_id,
                "dataset_version": DATASET_VERSION,
                "split": split,
                "invoice_file": relative_invoice,
                "synthetic": True,
                "contains_real_entity_data": False,
                "profile": "standard_tax_invoice_base",
                "generator_version": GENERATOR_VERSION,
                "seed": settings["seed"] + index * 1009,
                "validation_date": VALIDATION_DATE.isoformat(),
            })
            truth_records.append({
                "case_id": case_id,
                "expected_selected_checks_pass": not expected_rules,
                "expected_rule_ids": expected_rules,
                "expected_issue_count": len(expected_rules),
                "safe_auto_correction": bool(operator_names) and all(OPERATORS[name].safe_auto_correction for name in operator_names),
            })
            injection_records.append({
                "case_id": case_id,
                "injection_applied": bool(operator_names),
                "injection_count": len(operator_names),
                "injections": injection_details,
                "seed": settings["seed"] + index * 1009,
            })

        (dataset_root / "metadata" / f"{split}.jsonl").write_text("".join(map(json_line, metadata_records)), encoding="utf-8")
        (dataset_root / "error_injections" / f"{split}.jsonl").write_text("".join(map(json_line, injection_records)), encoding="utf-8")
        (truth_root / f"{split}.jsonl").write_text("".join(map(json_line, truth_records)), encoding="utf-8")
        manifest = {
            "dataset_version": DATASET_VERSION,
            "generator_version": GENERATOR_VERSION,
            "split": split,
            "case_count": len(schedule),
            "seed": settings["seed"],
            "cases": manifest_cases,
        }
        (dataset_root / "manifests" / f"{split}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    seal_inputs = {
        "manifest": dataset_root / "manifests" / "final_test.json",
        "metadata": dataset_root / "metadata" / "final_test.jsonl",
        "error_injections": dataset_root / "error_injections" / "final_test.jsonl",
        "ground_truth": truth_root / "final_test.jsonl",
    }
    seal = {
        "dataset_version": DATASET_VERSION,
        "split": "final_test",
        "sealed_before_evaluation": True,
        "files": {name: {"path": str(path.relative_to(data_root)), "sha256": sha256_bytes(path.read_bytes())} for name, path in seal_inputs.items()},
    }
    (dataset_root / "final_test_seal.json").write_text(
        json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ZATCA POC dataset v1.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()
    generate(args.data_root)
    print(f"Generated {sum(item['count'] for item in SPLITS.values())} cases under {args.data_root}")


if __name__ == "__main__":
    main()

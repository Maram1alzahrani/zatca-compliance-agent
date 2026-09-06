from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from pathlib import Path

import yaml

from src.models import CanonicalInvoice, InvoiceLine, InvoiceParty, InvoiceTotals, VatBreakdown


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "src" / "models" / "schemas" / "canonical_invoice.schema.json"
MAP_PATH = ROOT / "src" / "models" / "ubl_field_map.yaml"


def flatten_schema_fields(schema: dict) -> set[str]:
    fields = {
        key
        for key in schema["properties"]
        if key not in {"schema_version", "seller", "buyer", "lines", "vat_breakdowns", "totals"}
    }
    fields |= {f"seller.{key}" for key in schema["$defs"]["party"]["properties"]}
    fields |= {f"buyer.{key}" for key in schema["$defs"]["party"]["properties"]}
    fields |= {f"lines[].{key}" for key in schema["$defs"]["invoiceLine"]["properties"]}
    fields |= {
        f"vat_breakdowns[].{key}" for key in schema["$defs"]["vatBreakdown"]["properties"]
    }
    fields |= {f"totals.{key}" for key in schema["$defs"]["totals"]["properties"]}
    return fields


class InvoiceSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.mapping = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))

    def test_json_schema_and_mapping_documents_parse(self) -> None:
        self.assertEqual("object", self.schema["type"])
        self.assertEqual("1.0.0", self.mapping["mapping_version"])

    def test_every_canonical_business_field_has_a_ubl_mapping(self) -> None:
        schema_fields = flatten_schema_fields(self.schema)
        mapped_fields = set(self.mapping["fields"])
        self.assertEqual(schema_fields, mapped_fields)

    def test_every_mapping_has_business_term_and_absolute_xpath(self) -> None:
        for field_name, mapping in self.mapping["fields"].items():
            self.assertTrue(mapping["business_term"], field_name)
            self.assertTrue(mapping["xpath"].startswith("/ubl:Invoice/"), field_name)

    def test_decimal_values_are_preserved_as_text(self) -> None:
        decimal_schema = self.schema["$defs"]["nullableDecimalText"]
        self.assertIn("string", decimal_schema["type"])
        self.assertNotIn("number", decimal_schema["type"])
        line = InvoiceLine(quantity="0.1", net_price="0.2", net_amount="0.02")
        self.assertEqual("0.02", asdict(line)["net_amount"])

    def test_invalid_business_values_remain_representable(self) -> None:
        candidate = CanonicalInvoice(
            invoice_number=None,
            issue_date="not-a-date",
            invoice_type_code="999",
            transaction_code="bad",
            seller=InvoiceParty(name=None, vat_number="123"),
            buyer=None,
            lines=(InvoiceLine(quantity="-1", net_amount="999.999"),),
            vat_breakdowns=(VatBreakdown(category_code="UNKNOWN", rate="999"),),
            totals=InvoiceTotals(tax_amount="-5"),
        )
        self.assertEqual("999", candidate.invoice_type_code)
        self.assertIsNone(candidate.invoice_number)

    def test_raw_xml_and_ground_truth_are_not_schema_fields(self) -> None:
        serialized = json.dumps(self.schema)
        for forbidden in ("raw_xml", "ground_truth", "label", "error_injection"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()


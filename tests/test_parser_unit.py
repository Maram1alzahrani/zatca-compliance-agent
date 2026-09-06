from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.parsers import parse_invoice


ROOT = Path(__file__).resolve().parents[1]
BASELINE_XML = ROOT / "data" / "synthetic" / "dev" / "invoices" / "inv_0001.xml"


class UblParserUnitTests(unittest.TestCase):
    def test_baseline_maps_selected_canonical_fields(self) -> None:
        outcome = parse_invoice(BASELINE_XML)
        self.assertIsNone(outcome.error)
        self.assertIsNotNone(outcome.invoice)
        invoice = outcome.invoice
        assert invoice is not None
        self.assertEqual("SYN-20260001", invoice.invoice_number)
        self.assertEqual("388", invoice.invoice_type_code)
        self.assertEqual("0100000", invoice.transaction_code)
        self.assertEqual("310000000000003", invoice.seller.vat_number if invoice.seller else None)
        self.assertEqual(2, len(invoice.lines))
        self.assertEqual("140.00", invoice.totals.line_extension_amount if invoice.totals else None)

    def test_missing_file_returns_structured_failure(self) -> None:
        outcome = parse_invoice(Path("does-not-exist.xml"))
        self.assertIsNone(outcome.invoice)
        self.assertIsNone(outcome.document)
        self.assertIsNotNone(outcome.error)

    def test_non_invoice_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-invoice.xml"
            path.write_text("<Order/>", encoding="utf-8")
            outcome = parse_invoice(path)
        self.assertIsNone(outcome.invoice)
        self.assertIsNotNone(outcome.document)
        self.assertEqual("Root element is not UBL Invoice-2", outcome.error)

    def test_external_entity_is_not_expanded(self) -> None:
        payload = b'''<?xml version="1.0"?>
<!DOCTYPE Invoice [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>&xxe;</cbc:ID>
</Invoice>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entity.xml"
            path.write_bytes(payload)
            outcome = parse_invoice(path)
        self.assertIsNotNone(outcome.invoice)
        assert outcome.invoice is not None
        self.assertIsNone(outcome.invoice.invoice_number)

    def test_whitespace_only_text_normalizes_to_missing(self) -> None:
        payload = b'''<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>   </cbc:ID>
</Invoice>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.xml"
            path.write_bytes(payload)
            outcome = parse_invoice(path)
        self.assertIsNotNone(outcome.invoice)
        assert outcome.invoice is not None
        self.assertIsNone(outcome.invoice.invoice_number)


if __name__ == "__main__":
    unittest.main()

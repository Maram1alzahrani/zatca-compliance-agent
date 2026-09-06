from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from app.service import MAX_UPLOAD_BYTES, DemoService, UploadValidationError, validate_upload


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "synthetic" / "v1" / "development" / "invoices"
VALIDATION_DATE = date(2026, 9, 6)


class UploadValidationTests(unittest.TestCase):
    def test_rejects_wrong_extension_empty_oversized_and_non_xml_content(self) -> None:
        with self.assertRaises(UploadValidationError):
            validate_upload("invoice.txt", b"<Invoice/>")
        with self.assertRaises(UploadValidationError):
            validate_upload("invoice.xml", b"")
        with self.assertRaises(UploadValidationError):
            validate_upload("invoice.xml", b"x" * (MAX_UPLOAD_BYTES + 1))
        with self.assertRaises(UploadValidationError):
            validate_upload("invoice.xml", b"not xml")

    def test_accepts_xml_case_insensitively(self) -> None:
        validate_upload("SYNTHETIC.XML", b"<Invoice/>")


class DemoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DemoService()

    def test_compliant_upload_runs_without_using_display_name_as_path(self) -> None:
        payload = (DEV / "invoice_0002.xml").read_bytes()
        result = self.service.analyze(
            display_filename="../../synthetic-demo.xml",
            payload=payload,
            validation_date=VALIDATION_DATE,
        )
        self.assertTrue(result.analysis["selected_checks_pass"])
        self.assertEqual("synthetic-demo.xml", result.report["invoice"]["display_filename"])
        self.assertIn(b"Passed the selected checks", result.report_markdown)

    def test_issue_report_contains_verified_evidence_and_recommendation(self) -> None:
        payload = (DEV / "invoice_0003.xml").read_bytes()
        result = self.service.analyze(
            display_filename="invoice.xml", payload=payload, validation_date=VALIDATION_DATE
        )
        issue = result.report["detected_issues"][0]
        self.assertEqual("VERIFIED", issue["evidence_status"])
        self.assertTrue(issue["sources"])
        self.assertTrue(issue["suggested_action"])

    def test_no_approval_produces_no_corrected_xml(self) -> None:
        payload = (DEV / "invoice_0013.xml").read_bytes()
        result = self.service.correct_and_revalidate(
            display_filename="invoice.xml",
            payload=payload,
            validation_date=VALIDATION_DATE,
            approved=False,
        )
        self.assertIsNone(result.corrected_xml)
        self.assertEqual("AWAITING_APPROVAL", result.correction["status"])
        self.assertIsNone(result.report["revalidation"])

    def test_approved_safe_correction_returns_copy_and_revalidation_report(self) -> None:
        payload = (DEV / "invoice_0013.xml").read_bytes()
        result = self.service.correct_and_revalidate(
            display_filename="invoice.xml",
            payload=payload,
            validation_date=VALIDATION_DATE,
            approved=True,
        )
        self.assertIsNotNone(result.corrected_xml)
        self.assertNotEqual(payload, result.corrected_xml)
        self.assertTrue(result.report["revalidation"]["after_selected_checks_pass"])
        self.assertTrue(result.report["revalidation"]["original_preserved"])
        self.assertEqual([], result.report["revalidation"]["introduced_rule_ids"])


if __name__ == "__main__":
    unittest.main()

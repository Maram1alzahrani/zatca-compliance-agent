from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from app.service import DemoService
from src.agent.explainers import BANNED_CLAIMS
from src.reporting import PASS_CONCLUSION, build_compliance_report, render_report_markdown


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "data" / "synthetic" / "v1" / "development" / "invoices"


class ComplianceReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demo = DemoService().analyze(
            display_filename="synthetic.xml",
            payload=(DEV / "invoice_0013.xml").read_bytes(),
            validation_date=date(2026, 9, 6),
        )

    def test_report_contains_required_sections(self) -> None:
        report = self.demo.report
        self.assertEqual(8, len(report["checks_performed"]))
        self.assertTrue(report["passed_rule_ids"])
        self.assertTrue(report["detected_issues"])
        self.assertIn("disclaimer", report)
        self.assertIn("correction_proposal", report)

    def test_internal_severity_is_labeled_as_internal(self) -> None:
        self.assertTrue(
            all(item["severity_authority"] == "INTERNAL_POC" for item in self.demo.report["detected_issues"])
        )

    def test_report_avoids_prohibited_approval_claims(self) -> None:
        combined = (self.demo.report_json + self.demo.report_markdown).decode("utf-8").lower()
        self.assertTrue(all(claim not in combined for claim in BANNED_CLAIMS))

    def test_passing_report_uses_bounded_conclusion(self) -> None:
        passing = DemoService().analyze(
            display_filename="synthetic.xml",
            payload=(DEV / "invoice_0002.xml").read_bytes(),
            validation_date=date(2026, 9, 6),
        )
        self.assertEqual(PASS_CONCLUSION, passing.report["conclusion"])
        rebuilt = build_compliance_report(passing.analysis, display_filename="synthetic.xml")
        self.assertIn(PASS_CONCLUSION, render_report_markdown(rebuilt))


if __name__ == "__main__":
    unittest.main()

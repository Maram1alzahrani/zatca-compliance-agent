from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.validators import CheckStatus, validate_invoice
from src.validators.checks import RULE_IDS


ROOT = Path(__file__).resolve().parents[1]
BASELINE_XML = ROOT / "data" / "synthetic" / "dev" / "invoices" / "inv_0001.xml"
VALIDATION_DATE = date(2026, 9, 6)


class ValidationOrchestratorUnitTests(unittest.TestCase):
    def test_report_contains_exactly_one_ordered_result_per_rule(self) -> None:
        report = validate_invoice(BASELINE_XML, validation_date=VALIDATION_DATE)
        self.assertEqual(RULE_IDS, tuple(check.rule_id for check in report.checks))
        self.assertEqual(len(RULE_IDS), len({check.rule_id for check in report.checks}))

    def test_unavailable_xsd_does_not_hide_independent_business_results(self) -> None:
        report = validate_invoice(
            BASELINE_XML,
            validation_date=VALIDATION_DATE,
            xsd_path=Path("missing-trusted-schema.xsd"),
        )
        self.assertIs(report.checks[0].status, CheckStatus.NOT_RUN)
        self.assertTrue(all(check.status is CheckStatus.PASS for check in report.checks[1:]))
        self.assertFalse(report.selected_checks_pass)

    def test_non_invoice_root_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "order.xml"
            path.write_text("<Order/>", encoding="utf-8")
            report = validate_invoice(path, validation_date=VALIDATION_DATE)
        self.assertIs(report.checks[0].status, CheckStatus.FAIL)
        self.assertTrue(all(check.status is CheckStatus.NOT_RUN for check in report.checks[1:]))
        self.assertFalse(report.selected_checks_pass)

    def test_missing_invoice_file_fails_closed(self) -> None:
        report = validate_invoice(Path("missing-invoice.xml"), validation_date=VALIDATION_DATE)
        self.assertIs(report.checks[0].status, CheckStatus.FAIL)
        self.assertTrue(all(check.status is CheckStatus.NOT_RUN for check in report.checks[1:]))
        self.assertFalse(report.selected_checks_pass)


if __name__ == "__main__":
    unittest.main()

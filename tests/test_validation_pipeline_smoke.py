from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from src.validators import CheckStatus, validate_invoice


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class ValidationPipelineSmokeTests(unittest.TestCase):
    def test_baseline_passes_all_selected_checks(self) -> None:
        report = validate_invoice(
            DATA / "synthetic/dev/invoices/inv_0001.xml",
            validation_date=date(2026, 9, 6),
        )
        self.assertTrue(report.selected_checks_pass)
        self.assertTrue(all(check.status is CheckStatus.PASS for check in report.checks))

    def test_malformed_xml_fails_closed(self) -> None:
        report = validate_invoice(
            DATA / "synthetic/dev/invoices/inv_0002.xml",
            validation_date=date(2026, 9, 6),
        )
        self.assertFalse(report.selected_checks_pass)
        self.assertIs(report.checks[0].status, CheckStatus.FAIL)
        self.assertTrue(all(check.status is CheckStatus.NOT_RUN for check in report.checks[1:]))

    def test_development_predictions_match_ground_truth_rule_ids(self) -> None:
        truth = {
            record["case_id"]: record
            for record in (
                json.loads(line)
                for line in (DATA / "ground_truth/dev.jsonl").read_text().splitlines()
            )
        }
        manifest = json.loads((DATA / "synthetic/manifests/dev_manifest.json").read_text())
        for case in manifest["cases"]:
            report = validate_invoice(
                DATA / case["invoice_file"],
                validation_date=date(2026, 9, 6),
            )
            predicted = {check.rule_id for check in report.checks if check.status is CheckStatus.FAIL}
            self.assertEqual(set(truth[case["case_id"]]["expected_rule_ids"]), predicted, case["case_id"])


if __name__ == "__main__":
    unittest.main()


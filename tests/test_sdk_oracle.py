from __future__ import annotations

import unittest
from pathlib import Path

from evaluation.sdk_oracle import (
    SdkOracleResult,
    build_sdk_command,
    parse_sdk_global_result,
    summarize,
)


class SdkOutputParserTests(unittest.TestCase):
    def test_parses_passed_global_result(self) -> None:
        output = "InvoiceValidationService - *** GLOBAL VALIDATION RESULT - PASSED"
        self.assertEqual("PASSED", parse_sdk_global_result(output))

    def test_parses_failed_global_result_case_insensitively(self) -> None:
        output = "global validation result - failed"
        self.assertEqual("FAILED", parse_sdk_global_result(output))

    def test_missing_global_result_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_sdk_global_result("validation finished")

    def test_conflicting_results_fail_closed(self) -> None:
        output = (
            "GLOBAL VALIDATION RESULT - PASSED\n"
            "GLOBAL VALIDATION RESULT - FAILED"
        )
        with self.assertRaises(ValueError):
            parse_sdk_global_result(output)


class SdkCommandTests(unittest.TestCase):
    def test_command_requires_exactly_one_invoice_placeholder(self) -> None:
        with self.assertRaises(ValueError):
            build_sdk_command("fatoora validate", Path("invoice.xml"))
        with self.assertRaises(ValueError):
            build_sdk_command("tool {invoice} {invoice}", Path("invoice.xml"))

    def test_command_builds_argv_without_shell(self) -> None:
        command = build_sdk_command(
            'java -jar "sdk tool.jar" {invoice}',
            Path("invoice.xml"),
        )
        self.assertEqual("java", command[0])
        self.assertEqual("-jar", command[1])
        self.assertEqual("sdk tool.jar", command[2])
        self.assertTrue(command[3].endswith("invoice.xml"))


class SummaryTests(unittest.TestCase):
    def test_summary_reports_disagreements(self) -> None:
        items = (
            SdkOracleResult(
                invoice="a.xml",
                sdk_status="PASSED",
                poc_selected_checks_pass=True,
                agreement=True,
                failed_rule_ids=(),
                command=("sdk",),
                returncode=0,
                stdout="",
                stderr="",
            ),
            SdkOracleResult(
                invoice="b.xml",
                sdk_status="FAILED",
                poc_selected_checks_pass=True,
                agreement=False,
                failed_rule_ids=(),
                command=("sdk",),
                returncode=0,
                stdout="",
                stderr="",
            ),
        )
        summary = summarize(items)
        self.assertEqual(2, summary["cases"])
        self.assertEqual(1, summary["agreements"])
        self.assertEqual(0.5, summary["agreement_rate"])
        self.assertEqual(1, len(summary["disagreements"]))


if __name__ == "__main__":
    unittest.main()

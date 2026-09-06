from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.audit_correction_workflow import audit
from src.agent import ComplianceAgent, CorrectionWorkflowStatus
from src.corrections import CorrectionDisposition, CorrectionSafetyError


ROOT = Path(__file__).resolve().parents[1]
INVOICES = ROOT / "data" / "synthetic" / "v1" / "development" / "invoices"
VALIDATION_DATE = date(2026, 9, 6)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SafeCorrectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = ComplianceAgent()

    def test_compliant_invoice_has_no_correction_proposal(self) -> None:
        result = self.agent.analyze(INVOICES / "invoice_0002.xml", validation_date=VALIDATION_DATE)
        self.assertIsNone(result.correction_proposal)

    def test_calculation_only_failure_gets_deterministic_source_bound_patches(self) -> None:
        result = self.agent.analyze(INVOICES / "invoice_0013.xml", validation_date=VALIDATION_DATE)
        proposal = result.correction_proposal
        self.assertIsNotNone(proposal)
        self.assertTrue(proposal.eligible)
        self.assertEqual(2, len(proposal.patches))
        self.assertEqual(
            {"lines[0].net_amount", "vat_breakdowns[0].tax_amount"},
            {item.field for item in proposal.patches},
        )
        self.assertEqual(digest(INVOICES / "invoice_0013.xml"), proposal.source_sha256)
        self.assertNotIn("ground_truth", json.dumps(proposal.to_dict()).lower())

    def test_business_data_failure_is_human_required_and_never_patched(self) -> None:
        result = self.agent.analyze(INVOICES / "invoice_0003.xml", validation_date=VALIDATION_DATE)
        proposal = result.correction_proposal
        self.assertFalse(proposal.eligible)
        self.assertEqual((), proposal.patches)
        self.assertEqual(("MVP-DATE-001",), proposal.blocked_by_rule_ids)
        self.assertIs(proposal.recommendations[0].disposition, CorrectionDisposition.HUMAN_REQUIRED)

    def test_mixed_safe_and_unsafe_failures_are_not_partially_auto_applied(self) -> None:
        result = self.agent.analyze(INVOICES / "invoice_0008.xml", validation_date=VALIDATION_DATE)
        proposal = result.correction_proposal
        self.assertFalse(proposal.eligible)
        self.assertEqual((), proposal.patches)
        self.assertIn("MVP-SELLER-001", proposal.blocked_by_rule_ids)

    def test_no_approval_means_no_file_is_written(self) -> None:
        source = INVOICES / "invoice_0013.xml"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "corrected.xml"
            result = self.agent.correct_and_revalidate(
                source, validation_date=VALIDATION_DATE, approved=False, output_path=output
            )
            self.assertIs(result.status, CorrectionWorkflowStatus.AWAITING_APPROVAL)
            self.assertFalse(output.exists())
            self.assertEqual((), result.after_checks)

    def test_approved_workflow_writes_copy_preserves_original_and_passes_revalidation(self) -> None:
        source = INVOICES / "invoice_0013.xml"
        before = digest(source)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "corrected.xml"
            result = self.agent.correct_and_revalidate(
                source, validation_date=VALIDATION_DATE, approved=True, output_path=output
            )
            self.assertIs(result.status, CorrectionWorkflowStatus.APPLIED_AND_REVALIDATED)
            self.assertTrue(output.exists())
            self.assertTrue(result.original_preserved)
            self.assertEqual(before, digest(source))
            self.assertNotEqual(before, digest(output))
            self.assertTrue(result.comparison.after_selected_checks_pass)
            self.assertEqual((), result.comparison.remaining_rule_ids)
            self.assertEqual((), result.comparison.introduced_rule_ids)
            self.assertEqual(
                ["apply_safe_correction", "revalidate_invoice"],
                [event.tool_name for event in result.tool_trace[-2:]],
            )

    def test_approval_requires_explicit_output_path(self) -> None:
        with self.assertRaises(ValueError):
            self.agent.correct_and_revalidate(
                INVOICES / "invoice_0013.xml", validation_date=VALIDATION_DATE, approved=True
            )

    def test_existing_output_is_never_overwritten(self) -> None:
        source = INVOICES / "invoice_0013.xml"
        proposal = self.agent.analyze(source, validation_date=VALIDATION_DATE).correction_proposal
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "exists.xml"
            output.write_text("keep me", encoding="utf-8")
            with self.assertRaises(CorrectionSafetyError):
                self.agent.correction_engine.apply(source, proposal, output)
            self.assertEqual("keep me", output.read_text(encoding="utf-8"))

    def test_original_path_cannot_be_used_as_output(self) -> None:
        source = INVOICES / "invoice_0013.xml"
        proposal = self.agent.analyze(source, validation_date=VALIDATION_DATE).correction_proposal
        with self.assertRaises(CorrectionSafetyError):
            self.agent.correction_engine.apply(source, proposal, source)

    def test_source_change_after_proposal_is_detected(self) -> None:
        original = INVOICES / "invoice_0013.xml"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.xml"
            source.write_bytes(original.read_bytes())
            proposal = self.agent.analyze(source, validation_date=VALIDATION_DATE).correction_proposal
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaises(CorrectionSafetyError):
                self.agent.correction_engine.apply(source, proposal, Path(directory) / "fixed.xml")

    def test_malformed_xml_is_manual_only(self) -> None:
        result = self.agent.analyze(INVOICES / "invoice_0037.xml", validation_date=VALIDATION_DATE)
        self.assertFalse(result.correction_proposal.eligible)
        self.assertEqual((), result.correction_proposal.patches)

    def test_correction_audit_matches_development_and_validation_ground_truth(self) -> None:
        summary = audit(ROOT / "data")
        self.assertEqual(48, summary["development"]["cases"])
        self.assertEqual(32, summary["validation"]["cases"])
        self.assertTrue(all(item["passed"] for item in summary.values()))

    def test_correction_audit_refuses_final_test(self) -> None:
        with self.assertRaises(ValueError):
            audit(ROOT / "data", ("final_test",))


if __name__ == "__main__":
    unittest.main()

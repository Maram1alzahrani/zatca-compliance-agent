from __future__ import annotations

import json
import unittest
from datetime import date
from pathlib import Path

from src.agent import ComplianceAgent, GeneratedNarrative, OpenAIExplanationProvider
from src.tools import ToolCallStatus, UnknownToolError
from src.validators import CheckStatus
from scripts.audit_agent_workflow import audit


ROOT = Path(__file__).resolve().parents[1]
INVOICES = ROOT / "data" / "synthetic" / "dev" / "invoices"
VALIDATION_DATE = date(2026, 9, 6)


class ValidFakeProvider:
    def __init__(self) -> None:
        self.payload = None

    def generate(self, payload):
        self.payload = payload
        return tuple(
            GeneratedNarrative(
                item["rule_id"],
                f"صياغة موثقة للمشكلة {item['rule_id']}",
                "تم رصدها بواسطة نتيجة الفحص الحتمي المرفقة.",
            )
            for item in payload["rules"]
            if item["verified_evidence"] is not None
        )


class WrongRuleProvider:
    def generate(self, payload):
        return (GeneratedNarrative("MVP-NOT-REAL", "Issue", "Reason"),)


class ProhibitedClaimProvider:
    def generate(self, payload):
        rule_id = payload["rules"][0]["rule_id"]
        return (GeneratedNarrative(rule_id, "ZATCA Approved", "Officially compliant"),)


class FailingProvider:
    def generate(self, payload):
        raise RuntimeError("synthetic provider failure")


class ComplianceAgentOrchestrationTests(unittest.TestCase):
    def test_compliant_invoice_runs_validation_only(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0001.xml", validation_date=VALIDATION_DATE)
        self.assertTrue(result.selected_checks_pass)
        self.assertEqual((), result.issues)
        self.assertEqual("not_required", result.explanation_mode)
        self.assertEqual(["validate_invoice"], [event.tool_name for event in result.tool_trace])

    def test_single_failure_runs_required_tools_in_order(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE)
        self.assertEqual(
            ["validate_invoice", "retrieve_zatca_rule", "explain_issues", "propose_safe_correction"],
            [event.tool_name for event in result.tool_trace],
        )
        self.assertTrue(all(event.status is ToolCallStatus.SUCCESS for event in result.tool_trace))
        self.assertEqual("MVP-SELLER-001", result.issues[0].rule_id)

    def test_each_failed_rule_gets_one_exact_evidence_retrieval(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0003.xml", validation_date=VALIDATION_DATE)
        failed = [check.rule_id for check in result.checks if check.status is CheckStatus.FAIL]
        retrieved = [
            event.input_summary["rule_id"]
            for event in result.tool_trace
            if event.tool_name == "retrieve_zatca_rule"
        ]
        self.assertEqual(failed, retrieved)
        self.assertEqual(failed, [issue.rule_id for issue in result.issues])

    def test_parse_failure_explains_xml_and_preserves_not_run_checks(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0002.xml", validation_date=VALIDATION_DATE)
        self.assertEqual(["MVP-XML-001"], [issue.rule_id for issue in result.issues])
        self.assertEqual(7, sum(check.status is CheckStatus.NOT_RUN for check in result.checks))
        self.assertEqual(1, sum(event.tool_name == "retrieve_zatca_rule" for event in result.tool_trace))

    def test_issue_evidence_is_verified_and_source_grounded(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0011.xml", validation_date=VALIDATION_DATE)
        issue = result.issues[0]
        self.assertEqual("VERIFIED", issue.evidence_status)
        self.assertEqual("MVP-VAT-TOTAL-001", issue.rule_id)
        self.assertTrue(issue.official_identifiers)
        self.assertTrue(issue.sources)
        self.assertTrue(all(source.url.startswith("https://zatca.gov.sa/") for source in issue.sources))

    def test_valid_llm_narrative_is_used_but_citations_remain_deterministic(self) -> None:
        provider = ValidFakeProvider()
        result = ComplianceAgent(explanation_provider=provider).analyze(
            INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE
        )
        self.assertEqual("llm", result.explanation_mode)
        self.assertEqual("llm", result.issues[0].narrative_mode)
        self.assertIn("صياغة موثقة", result.issues[0].issue)
        self.assertTrue(result.issues[0].sources)
        self.assertEqual({"task", "rules"}, set(provider.payload))
        self.assertNotIn("ground_truth", json.dumps(provider.payload, ensure_ascii=False).lower())

    def test_wrong_rule_from_llm_triggers_deterministic_fallback(self) -> None:
        result = ComplianceAgent(explanation_provider=WrongRuleProvider()).analyze(
            INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE
        )
        self.assertEqual("fallback", result.explanation_mode)
        self.assertEqual("ValueError", result.fallback_reason)
        self.assertEqual("deterministic", result.issues[0].narrative_mode)

    def test_prohibited_approval_claim_triggers_fallback(self) -> None:
        result = ComplianceAgent(explanation_provider=ProhibitedClaimProvider()).analyze(
            INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE
        )
        self.assertEqual("fallback", result.explanation_mode)
        self.assertNotIn("ZATCA Approved", result.issues[0].issue)

    def test_provider_failure_is_contained_and_recorded(self) -> None:
        result = ComplianceAgent(explanation_provider=FailingProvider()).analyze(
            INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE
        )
        self.assertEqual("fallback", result.explanation_mode)
        self.assertEqual("RuntimeError", result.fallback_reason)
        self.assertTrue(all(event.status is ToolCallStatus.SUCCESS for event in result.tool_trace))

    def test_unknown_tool_call_is_rejected_and_audited(self) -> None:
        agent = ComplianceAgent()
        trace = []
        with self.assertRaises(UnknownToolError):
            agent.tools.execute("invented_tool", {}, trace)
        self.assertEqual(1, len(trace))
        self.assertIs(trace[0].status, ToolCallStatus.FAILED)
        self.assertEqual("UnknownToolError", trace[0].error_type)

    def test_analysis_is_json_serializable_and_contains_bounded_correction_contract(self) -> None:
        result = ComplianceAgent().analyze(INVOICES / "inv_0007.xml", validation_date=VALIDATION_DATE)
        encoded = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertIn("MVP-SELLER-001", encoded)
        self.assertIn("correction_proposal", encoded)
        self.assertNotIn("corrected_invoice", encoded)

    def test_openai_provider_requires_explicit_model_and_supported_language(self) -> None:
        with self.assertRaises(ValueError):
            OpenAIExplanationProvider("")
        with self.assertRaises(ValueError):
            OpenAIExplanationProvider("explicit-model", "fr")

    def test_scaled_development_and_validation_workflows_are_consistent(self) -> None:
        summary = audit(ROOT / "data")
        self.assertEqual(48, summary["development"]["cases"])
        self.assertEqual(32, summary["validation"]["cases"])
        self.assertTrue(all(item["passed"] for item in summary.values()))

    def test_agent_audit_refuses_final_test(self) -> None:
        with self.assertRaises(ValueError):
            audit(ROOT / "data", ("final_test",))


if __name__ == "__main__":
    unittest.main()

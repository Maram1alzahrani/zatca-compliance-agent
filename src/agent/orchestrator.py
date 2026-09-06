from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path

from src.agent.explainers import ExplanationBatch, ExplanationProvider, GroundedExplanationService
from src.agent.models import (
    AgentAnalysis,
    CorrectionWorkflowResult,
    CorrectionWorkflowStatus,
    RevalidationComparison,
)
from src.corrections import CorrectionEngine
from src.rag import VerifiedRuleRetriever
from src.rag.models import RuleEvidence
from src.tools import ToolCallEvent
from src.tools.compliance import build_compliance_tool_registry
from src.validators import CheckStatus


LIMITATIONS = (
    "Educational portfolio proof of concept using selected checks only.",
    "Not affiliated with ZATCA and not legal or tax advice.",
    "Does not imply ZATCA approval, certification, clearance, reporting, or full compliance.",
    "Corrections are limited to deterministic derived monetary values in the frozen MVP profile.",
    "The original invoice is never overwritten and explicit approval is required before creating a corrected copy.",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ComplianceAgent:
    """Single workflow agent with deterministic mandatory tool selection."""

    def __init__(
        self,
        *,
        retriever: VerifiedRuleRetriever | None = None,
        explanation_provider: ExplanationProvider | None = None,
    ) -> None:
        self.retriever = retriever or VerifiedRuleRetriever()
        self.explanation_service = GroundedExplanationService(explanation_provider)
        self.correction_engine = CorrectionEngine()
        self.tools = build_compliance_tool_registry(
            self.retriever, self.explanation_service, self.correction_engine
        )

    def analyze(self, invoice_path: Path, *, validation_date: date) -> AgentAnalysis:
        trace: list[ToolCallEvent] = []
        report = self.tools.execute(
            "validate_invoice",
            {"invoice_path": Path(invoice_path), "validation_date": validation_date},
            trace,
        )
        findings = tuple(check for check in report.checks if check.status is CheckStatus.FAIL)
        evidence_by_rule: dict[str, RuleEvidence | None] = {}
        for finding in findings:
            response = self.tools.execute(
                "retrieve_zatca_rule",
                {"rule_id": finding.rule_id},
                trace,
            )
            evidence_by_rule[finding.rule_id] = response.hits[0].evidence if response.hits else None

        if findings:
            explanations: ExplanationBatch = self.tools.execute(
                "explain_issues",
                {"findings": findings, "evidence_by_rule": evidence_by_rule},
                trace,
            )
        else:
            explanations = ExplanationBatch((), "not_required", None)

        proposal = None
        if findings:
            proposal = self.tools.execute(
                "propose_safe_correction",
                {"invoice_path": Path(invoice_path), "report": report},
                trace,
            )

        return AgentAnalysis(
            schema_version="1.1.0",
            invoice_file=str(invoice_path),
            invoice_identifier=report.invoice_identifier,
            selected_checks_pass=report.selected_checks_pass,
            checks=report.checks,
            issues=explanations.issues,
            tool_trace=tuple(trace),
            explanation_mode=explanations.mode,
            fallback_reason=explanations.fallback_reason,
            correction_proposal=proposal,
            limitations=LIMITATIONS,
        )

    def correct_and_revalidate(
        self,
        invoice_path: Path,
        *,
        validation_date: date,
        approved: bool,
        output_path: Path | None = None,
    ) -> CorrectionWorkflowResult:
        invoice_path = Path(invoice_path)
        analysis = self.analyze(invoice_path, validation_date=validation_date)
        proposal = analysis.correction_proposal
        trace = list(analysis.tool_trace)
        original_hash = _sha256(invoice_path)
        if proposal is None or not proposal.eligible:
            return CorrectionWorkflowResult(
                "1.0.0",
                CorrectionWorkflowStatus.NOT_APPLICABLE,
                approved,
                str(invoice_path),
                None,
                original_hash,
                None,
                _sha256(invoice_path) == original_hash,
                proposal,
                None,
                analysis.checks,
                (),
                tuple(trace),
                LIMITATIONS,
            )
        if not approved:
            return CorrectionWorkflowResult(
                "1.0.0",
                CorrectionWorkflowStatus.AWAITING_APPROVAL,
                False,
                str(invoice_path),
                None,
                original_hash,
                None,
                _sha256(invoice_path) == original_hash,
                proposal,
                None,
                analysis.checks,
                (),
                tuple(trace),
                LIMITATIONS,
            )
        if output_path is None:
            raise ValueError("output_path is required after approval.")

        corrected_path = self.tools.execute(
            "apply_safe_correction",
            {"invoice_path": invoice_path, "proposal": proposal, "output_path": Path(output_path)},
            trace,
        )
        after = self.tools.execute(
            "revalidate_invoice",
            {"invoice_path": corrected_path, "validation_date": validation_date},
            trace,
        )
        before_failed = {check.rule_id for check in analysis.checks if check.status is CheckStatus.FAIL}
        after_failed = {check.rule_id for check in after.checks if check.status is CheckStatus.FAIL}
        comparison = RevalidationComparison(
            analysis.selected_checks_pass,
            after.selected_checks_pass,
            tuple(sorted(before_failed - after_failed)),
            tuple(sorted(before_failed & after_failed)),
            tuple(sorted(after_failed - before_failed)),
        )
        return CorrectionWorkflowResult(
            "1.0.0",
            CorrectionWorkflowStatus.APPLIED_AND_REVALIDATED,
            True,
            str(invoice_path),
            str(corrected_path),
            original_hash,
            _sha256(corrected_path),
            _sha256(invoice_path) == original_hash,
            proposal,
            comparison,
            analysis.checks,
            after.checks,
            tuple(trace),
            LIMITATIONS,
        )

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.corrections import CorrectionEngine
from src.rag import RetrievalResponse, VerifiedRuleRetriever
from src.rag.models import RuleEvidence
from src.tools.registry import ToolDefinition, ToolRegistry
from src.validators import CheckResult, ValidationReport, validate_invoice

if TYPE_CHECKING:
    from src.agent.explainers import GroundedExplanationService


def build_compliance_tool_registry(
    retriever: VerifiedRuleRetriever,
    explanation_service: "GroundedExplanationService",
    correction_engine: CorrectionEngine,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="validate_invoice",
            description="Securely parse an invoice and run all eight deterministic selected checks.",
            handler=lambda invoice_path, validation_date: validate_invoice(invoice_path, validation_date=validation_date),
            summarize_input=lambda value: {
                "invoice_file": Path(value["invoice_path"]).name,
                "validation_date": value["validation_date"].isoformat(),
                "includes_secure_parse": True,
            },
            summarize_output=lambda report: {
                "checks": len(report.checks),
                "failed": sum(check.status.value == "FAIL" for check in report.checks),
                "not_run": sum(check.status.value == "NOT_RUN" for check in report.checks),
                "selected_checks_pass": report.selected_checks_pass,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="retrieve_zatca_rule",
            description="Retrieve one verified ZATCA evidence record by internal rule ID.",
            handler=lambda rule_id: retriever.retrieve_rule(rule_id),
            summarize_input=lambda value: {"rule_id": value["rule_id"]},
            summarize_output=lambda response: {
                "hits": len(response.hits),
                "verified_only": response.verified_only,
                "matched_rule_id": response.hits[0].evidence.internal_rule_id if response.hits else None,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="explain_issues",
            description="Create bounded narratives from validator findings and retrieved verified evidence.",
            handler=lambda findings, evidence_by_rule: explanation_service.explain(findings, evidence_by_rule),
            summarize_input=lambda value: {
                "finding_rule_ids": [finding.rule_id for finding in value["findings"]],
                "verified_evidence_count": sum(item is not None for item in value["evidence_by_rule"].values()),
            },
            summarize_output=lambda batch: {
                "issues": len(batch.issues),
                "mode": batch.mode,
                "fallback_reason": batch.fallback_reason,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="propose_safe_correction",
            description="Build a source-bound correction proposal using deterministic calculations only.",
            handler=lambda invoice_path, report: correction_engine.propose(invoice_path, report),
            summarize_input=lambda value: {
                "invoice_file": Path(value["invoice_path"]).name,
                "failed_rule_ids": [
                    check.rule_id for check in value["report"].checks if check.status.value == "FAIL"
                ],
            },
            summarize_output=lambda proposal: {
                "proposal_id": proposal.proposal_id,
                "eligible": proposal.eligible,
                "patch_count": len(proposal.patches),
                "blocked_by_rule_ids": list(proposal.blocked_by_rule_ids),
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="apply_safe_correction",
            description="Apply an approved source-bound proposal to a new XML copy without overwriting the original.",
            handler=lambda invoice_path, proposal, output_path: correction_engine.apply(
                invoice_path, proposal, output_path
            ),
            summarize_input=lambda value: {
                "invoice_file": Path(value["invoice_path"]).name,
                "output_file": Path(value["output_path"]).name,
                "proposal_id": value["proposal"].proposal_id,
                "approval_handled_by_orchestrator": True,
            },
            summarize_output=lambda path: {"corrected_file": Path(path).name, "written_to_copy": True},
        )
    )
    registry.register(
        ToolDefinition(
            name="revalidate_invoice",
            description="Run the same deterministic validator suite on the corrected invoice copy.",
            handler=lambda invoice_path, validation_date: validate_invoice(
                invoice_path, validation_date=validation_date
            ),
            summarize_input=lambda value: {
                "invoice_file": Path(value["invoice_path"]).name,
                "validation_date": value["validation_date"].isoformat(),
            },
            summarize_output=lambda report: {
                "checks": len(report.checks),
                "failed": sum(check.status.value == "FAIL" for check in report.checks),
                "selected_checks_pass": report.selected_checks_pass,
            },
        )
    )
    return registry


__all__ = [
    "CheckResult",
    "RetrievalResponse",
    "RuleEvidence",
    "ValidationReport",
    "build_compliance_tool_registry",
]

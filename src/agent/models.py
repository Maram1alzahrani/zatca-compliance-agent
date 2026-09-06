from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.corrections import CorrectionProposal
from src.tools import ToolCallEvent
from src.validators.result import CheckResult


@dataclass(frozen=True, slots=True)
class SourceReference:
    title: str
    version: str | None
    date: str | None
    section: str
    pages: str | None
    url: str


@dataclass(frozen=True, slots=True)
class IssueExplanation:
    rule_id: str
    evidence_status: str
    internal_severity: str | None
    official_severity: str | None
    issue: str
    why_flagged: str
    applicable_requirement: str | None
    applicability: str | None
    official_identifiers: tuple[str, ...]
    sources: tuple[SourceReference, ...]
    narrative_mode: str


@dataclass(frozen=True, slots=True)
class AgentAnalysis:
    schema_version: str
    invoice_file: str
    invoice_identifier: str | None
    selected_checks_pass: bool
    checks: tuple[CheckResult, ...]
    issues: tuple[IssueExplanation, ...]
    tool_trace: tuple[ToolCallEvent, ...]
    explanation_mode: str
    fallback_reason: str | None
    correction_proposal: CorrectionProposal | None
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorrectionWorkflowStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPLIED_AND_REVALIDATED = "APPLIED_AND_REVALIDATED"


@dataclass(frozen=True, slots=True)
class RevalidationComparison:
    before_selected_checks_pass: bool
    after_selected_checks_pass: bool
    resolved_rule_ids: tuple[str, ...]
    remaining_rule_ids: tuple[str, ...]
    introduced_rule_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorrectionWorkflowResult:
    schema_version: str
    status: CorrectionWorkflowStatus
    approval_received: bool
    original_invoice_file: str
    corrected_invoice_file: str | None
    original_sha256: str
    corrected_sha256: str | None
    original_preserved: bool
    proposal: CorrectionProposal | None
    comparison: RevalidationComparison | None
    before_checks: tuple[CheckResult, ...]
    after_checks: tuple[CheckResult, ...]
    tool_trace: tuple[ToolCallEvent, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

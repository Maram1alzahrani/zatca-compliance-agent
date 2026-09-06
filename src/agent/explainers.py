from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from src.agent.models import IssueExplanation, SourceReference
from src.rag.models import RuleEvidence
from src.validators.result import CheckResult


@dataclass(frozen=True, slots=True)
class GeneratedNarrative:
    rule_id: str
    issue: str
    why_flagged: str


class ExplanationProvider(Protocol):
    def generate(self, payload: dict[str, Any]) -> tuple[GeneratedNarrative, ...]: ...


@dataclass(frozen=True, slots=True)
class ExplanationBatch:
    issues: tuple[IssueExplanation, ...]
    mode: str
    fallback_reason: str | None


BANNED_CLAIMS = (
    "zatca approved",
    "zatca certified",
    "officially compliant",
    "معتمد من زاتكا",
    "معتمد من هيئة الزكاة",
    "متوافق رسميا",
)
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


class GroundedExplanationService:
    def __init__(self, provider: ExplanationProvider | None = None) -> None:
        self.provider = provider

    def explain(
        self,
        findings: tuple[CheckResult, ...],
        evidence_by_rule: dict[str, RuleEvidence | None],
    ) -> ExplanationBatch:
        deterministic = self._build(findings, evidence_by_rule, {})
        if self.provider is None or not findings:
            return ExplanationBatch(deterministic, "deterministic", None)
        payload = {
            "task": "Rewrite only the issue and why_flagged fields using the supplied verified evidence.",
            "rules": [
                {
                    "rule_id": finding.rule_id,
                    "validator_message": finding.message,
                    "validator_details": list(finding.details),
                    "verified_evidence": evidence_by_rule[finding.rule_id].to_dict()
                    if evidence_by_rule.get(finding.rule_id)
                    else None,
                }
                for finding in findings
            ],
        }
        try:
            generated = self.provider.generate(payload)
            self._validate_generated(generated, findings, evidence_by_rule)
            narratives = {item.rule_id: item for item in generated}
            return ExplanationBatch(self._build(findings, evidence_by_rule, narratives), "llm", None)
        except Exception as exc:
            return ExplanationBatch(deterministic, "fallback", type(exc).__name__)

    @staticmethod
    def _validate_generated(
        generated: tuple[GeneratedNarrative, ...],
        findings: tuple[CheckResult, ...],
        evidence_by_rule: dict[str, RuleEvidence | None],
    ) -> None:
        expected = [finding.rule_id for finding in findings if evidence_by_rule.get(finding.rule_id)]
        actual = [item.rule_id for item in generated]
        if actual != expected:
            raise ValueError("LLM rule IDs do not exactly match grounded findings.")
        for item in generated:
            if not item.issue.strip() or not item.why_flagged.strip():
                raise ValueError("LLM narrative fields must not be empty.")
            combined = f"{item.issue} {item.why_flagged}".lower()
            if len(combined) > 4000 or URL_PATTERN.search(combined):
                raise ValueError("LLM narrative attempted an unsupported citation or excessive output.")
            if any(claim in combined for claim in BANNED_CLAIMS):
                raise ValueError("LLM narrative contains a prohibited approval/compliance claim.")

    @staticmethod
    def _build(
        findings: tuple[CheckResult, ...],
        evidence_by_rule: dict[str, RuleEvidence | None],
        narratives: dict[str, GeneratedNarrative],
    ) -> tuple[IssueExplanation, ...]:
        issues = []
        for finding in findings:
            evidence = evidence_by_rule.get(finding.rule_id)
            narrative = narratives.get(finding.rule_id)
            why = "; ".join(finding.details) if finding.details else finding.message
            if evidence is None:
                issues.append(
                    IssueExplanation(
                        rule_id=finding.rule_id,
                        evidence_status="NO_VERIFIED_EVIDENCE",
                        internal_severity=None,
                        official_severity=None,
                        issue=finding.message,
                        why_flagged=why,
                        applicable_requirement=None,
                        applicability=None,
                        official_identifiers=(),
                        sources=(),
                        narrative_mode="deterministic",
                    )
                )
                continue
            issues.append(
                IssueExplanation(
                    rule_id=finding.rule_id,
                    evidence_status="VERIFIED",
                    internal_severity=evidence.internal_severity,
                    official_severity=evidence.official_severity,
                    issue=narrative.issue if narrative else finding.message,
                    why_flagged=narrative.why_flagged if narrative else why,
                    applicable_requirement=evidence.meaning,
                    applicability=evidence.applicability,
                    official_identifiers=evidence.official_identifiers,
                    sources=tuple(
                        SourceReference(source.title, source.version, source.date, source.section, source.pages, source.url)
                        for source in evidence.sources
                    ),
                    narrative_mode="llm" if narrative else "deterministic",
                )
            )
        return tuple(issues)

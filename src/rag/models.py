from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_key: str
    title: str
    version: str | None
    date: str | None
    section: str
    pages: str | None
    url: str


@dataclass(frozen=True, slots=True)
class RuleEvidence:
    chunk_id: str
    internal_rule_id: str
    status: str
    decision_eligible: bool
    name: str
    official_identifiers: tuple[str, ...]
    applicability: str
    internal_severity: str
    official_severity: str | None
    meaning: str
    validation_logic: str
    sources: tuple[EvidenceSource, ...]
    retrieval_text: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RuleEvidence":
        return cls(
            chunk_id=value["chunk_id"],
            internal_rule_id=value["internal_rule_id"],
            status=value["status"],
            decision_eligible=value["decision_eligible"],
            name=value["name"],
            official_identifiers=tuple(value["official_identifiers"]),
            applicability=value["applicability"],
            internal_severity=value["internal_severity"],
            official_severity=value.get("official_severity"),
            meaning=value["meaning"],
            validation_logic=value["validation_logic"],
            sources=tuple(EvidenceSource(**source) for source in value["sources"]),
            retrieval_text=value["retrieval_text"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    rank: int
    score: float
    match_method: str
    evidence: RuleEvidence

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetrievalResponse:
    query: str
    method: str
    verified_only: bool
    hits: tuple[RetrievalHit, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

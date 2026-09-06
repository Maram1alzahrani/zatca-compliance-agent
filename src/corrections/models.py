from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CorrectionDisposition(str, Enum):
    AUTO_CALCULATED = "AUTO_CALCULATED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class CorrectionPatch:
    rule_id: str
    field: str
    xpath: str
    old_value: str
    new_value: str
    rationale: str


@dataclass(frozen=True, slots=True)
class CorrectionRecommendation:
    rule_id: str
    disposition: CorrectionDisposition
    suggested_action: str
    patch_count: int = 0


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    proposal_id: str
    source_sha256: str
    eligible: bool
    requires_human_approval: bool
    patches: tuple[CorrectionPatch, ...]
    recommendations: tuple[CorrectionRecommendation, ...]
    blocked_by_rule_ids: tuple[str, ...]
    safety_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

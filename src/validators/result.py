from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True, slots=True)
class CheckResult:
    rule_id: str
    status: CheckStatus
    message: str
    details: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    invoice_file: str
    invoice_identifier: str | None
    selected_checks_pass: bool
    checks: tuple[CheckResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


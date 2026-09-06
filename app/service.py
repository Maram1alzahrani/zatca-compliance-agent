from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.agent import ComplianceAgent
from src.reporting import build_compliance_report, render_report_markdown


MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class UploadValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DemoResult:
    analysis: dict[str, Any]
    correction: dict[str, Any] | None
    report: dict[str, Any]
    report_json: bytes
    report_markdown: bytes
    corrected_xml: bytes | None = None


def validate_upload(filename: str, payload: bytes) -> None:
    if Path(filename).suffix.lower() != ".xml":
        raise UploadValidationError("Only .xml invoice files are accepted.")
    if not payload:
        raise UploadValidationError("The uploaded XML file is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise UploadValidationError("The uploaded XML exceeds the 2 MB demo limit.")
    if b"<" not in payload or b">" not in payload:
        raise UploadValidationError("The uploaded content does not look like XML.")


class DemoService:
    """File-byte boundary used by Streamlit and tests; uploaded names never become paths."""

    def __init__(self, agent_factory=ComplianceAgent) -> None:
        self.agent_factory = agent_factory

    def analyze(
        self,
        *,
        display_filename: str,
        payload: bytes,
        validation_date: date,
    ) -> DemoResult:
        validate_upload(display_filename, payload)
        with TemporaryDirectory(prefix="zatca-demo-") as directory:
            invoice_path = Path(directory) / "uploaded_invoice.xml"
            invoice_path.write_bytes(payload)
            analysis = self.agent_factory().analyze(
                invoice_path, validation_date=validation_date
            ).to_dict()
        return self._result(analysis, display_filename=display_filename)

    def correct_and_revalidate(
        self,
        *,
        display_filename: str,
        payload: bytes,
        validation_date: date,
        approved: bool,
    ) -> DemoResult:
        validate_upload(display_filename, payload)
        with TemporaryDirectory(prefix="zatca-demo-") as directory:
            invoice_path = Path(directory) / "uploaded_invoice.xml"
            corrected_path = Path(directory) / "corrected_invoice.xml"
            invoice_path.write_bytes(payload)
            agent = self.agent_factory()
            analysis = agent.analyze(invoice_path, validation_date=validation_date).to_dict()
            workflow = agent.correct_and_revalidate(
                invoice_path,
                validation_date=validation_date,
                approved=approved,
                output_path=corrected_path if approved else None,
            )
            correction = workflow.to_dict()
            corrected_xml = corrected_path.read_bytes() if corrected_path.exists() else None
        return self._result(
            analysis,
            display_filename=display_filename,
            correction=correction,
            corrected_xml=corrected_xml,
        )

    @staticmethod
    def _result(
        analysis: dict[str, Any],
        *,
        display_filename: str,
        correction: dict[str, Any] | None = None,
        corrected_xml: bytes | None = None,
    ) -> DemoResult:
        report = build_compliance_report(
            analysis, display_filename=display_filename, correction=correction
        )
        return DemoResult(
            analysis=analysis,
            correction=correction,
            report=report,
            report_json=(json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            report_markdown=render_report_markdown(report).encode("utf-8"),
            corrected_xml=corrected_xml,
        )

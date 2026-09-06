from __future__ import annotations

import hashlib
import json
import os
import tempfile
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from lxml import etree

from src.corrections.models import (
    CorrectionDisposition,
    CorrectionPatch,
    CorrectionProposal,
    CorrectionRecommendation,
)
from src.parsers import parse_invoice
from src.parsers.ubl_invoice import NS
from src.validators import CheckStatus, ValidationReport


SAFE_DERIVED_RULES = frozenset({"MVP-LINE-001", "MVP-VAT-TOTAL-001"})
MANUAL_ACTIONS = {
    "MVP-XML-001": "Repair the XML structure using the originating invoicing system; no XML content is inferred.",
    "MVP-ID-001": "Provide the correct invoice number from the authoritative business record.",
    "MVP-DATE-001": "Confirm the actual issue date with an authorized reviewer before changing it.",
    "MVP-TYPE-001": "Confirm the legal invoice type and transaction subtype; the POC does not convert profiles.",
    "MVP-SELLER-001": "Obtain verified seller identity and VAT data from the authoritative master record.",
    "MVP-BUYER-001": "Obtain the buyer name from the authoritative customer record.",
    "MVP-LINE-001": "Review the commercial line inputs; automatic repair is unavailable unless every input is complete and valid.",
    "MVP-VAT-TOTAL-001": "Review VAT inputs and totals; automatic repair is unavailable unless every source value is complete and valid.",
}


class CorrectionSafetyError(ValueError):
    """Raised when an approved proposal cannot be applied without violating safety invariants."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal(value: str | None) -> Decimal:
    if value is None:
        raise CorrectionSafetyError("A required calculation input is missing.")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise CorrectionSafetyError("A calculation input is not a decimal.") from exc
    if not result.is_finite():
        raise CorrectionSafetyError("A calculation input is not finite.")
    return result


def _money(value: Decimal) -> str:
    try:
        return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")
    except DecimalException as exc:
        raise CorrectionSafetyError("A calculation exceeds supported decimal bounds.") from exc


def _patch(
    rule_id: str,
    field: str,
    xpath: str,
    old_value: str | None,
    new_value: str,
    rationale: str,
) -> CorrectionPatch | None:
    if old_value is None:
        raise CorrectionSafetyError(f"Correction target {field} is missing; insertion is not permitted.")
    if old_value == new_value:
        return None
    return CorrectionPatch(rule_id, field, xpath, old_value, new_value, rationale)


class CorrectionEngine:
    """Build and apply source-bound patches without using labels or an LLM."""

    def propose(self, invoice_path: Path, report: ValidationReport) -> CorrectionProposal:
        invoice_path = Path(invoice_path)
        source_hash = _sha256(invoice_path)
        failed = tuple(check.rule_id for check in report.checks if check.status is CheckStatus.FAIL)
        blocked = tuple(rule_id for rule_id in failed if rule_id not in SAFE_DERIVED_RULES)
        patches: tuple[CorrectionPatch, ...] = ()
        calculation_error: str | None = (
            "At least one prerequisite check was NOT_RUN."
            if any(check.status is CheckStatus.NOT_RUN for check in report.checks)
            else None
        )
        if failed and not blocked and calculation_error is None:
            try:
                patches = self._calculate_patches(invoice_path)
            except CorrectionSafetyError as exc:
                calculation_error = str(exc)

        eligible = bool(patches) and not blocked and calculation_error is None
        recommendations = []
        for rule_id in failed:
            rule_patches = tuple(item for item in patches if item.rule_id == rule_id)
            if eligible and rule_patches:
                recommendations.append(
                    CorrectionRecommendation(
                        rule_id,
                        CorrectionDisposition.AUTO_CALCULATED,
                        "Apply the listed deterministic derived-value patches to a copy after explicit human approval.",
                        len(rule_patches),
                    )
                )
            else:
                action = MANUAL_ACTIONS.get(rule_id, "Review this issue using the cited official requirement.")
                if calculation_error and rule_id in SAFE_DERIVED_RULES:
                    action = f"{action} Safety gate: {calculation_error}"
                recommendations.append(
                    CorrectionRecommendation(rule_id, CorrectionDisposition.HUMAN_REQUIRED, action)
                )

        payload = json.dumps(
            {
                "source_sha256": source_hash,
                "patches": [
                    {"rule_id": item.rule_id, "xpath": item.xpath, "old": item.old_value, "new": item.new_value}
                    for item in patches
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        proposal_id = hashlib.sha256(payload).hexdigest()[:20]
        note = (
            "Only deterministic monetary values derived from complete frozen-profile inputs are proposed; "
            "the original is immutable and approval is required before writing a copy."
        )
        return CorrectionProposal(
            proposal_id,
            source_hash,
            eligible,
            True,
            patches if eligible else (),
            tuple(recommendations),
            blocked,
            note,
        )

    def _calculate_patches(self, invoice_path: Path) -> tuple[CorrectionPatch, ...]:
        outcome = parse_invoice(invoice_path)
        if outcome.invoice is None or outcome.document is None:
            raise CorrectionSafetyError("The XML must parse securely before correction.")
        invoice = outcome.invoice
        if not invoice.lines or len(invoice.vat_breakdowns) != 1 or invoice.totals is None:
            raise CorrectionSafetyError("The frozen profile requires lines, one VAT breakdown, and monetary totals.")
        breakdown = invoice.vat_breakdowns[0]
        if breakdown.category_code != "S" or any(line.vat_category_code != "S" for line in invoice.lines):
            raise CorrectionSafetyError("Only the frozen single standard-rated VAT category is supported.")

        patches: list[CorrectionPatch] = []
        expected_lines: list[Decimal] = []
        for index, line in enumerate(invoice.lines, start=1):
            quantity = _decimal(line.quantity)
            price = _decimal(line.net_price)
            base = _decimal(line.price_base_quantity or "1")
            allowance = _decimal(line.allowance_amount or "0")
            charge = _decimal(line.charge_amount or "0")
            if base == 0:
                raise CorrectionSafetyError("A line base quantity is zero.")
            expected = Decimal(_money((price / base) * quantity - allowance + charge))
            expected_lines.append(expected)
            candidate = _patch(
                "MVP-LINE-001",
                f"lines[{index - 1}].net_amount",
                f"cac:InvoiceLine[{index}]/cbc:LineExtensionAmount",
                line.net_amount,
                _money(expected),
                "BT-131 is deterministically derived from quantity, net price, base quantity, charges, and allowances.",
            )
            if candidate:
                patches.append(candidate)

        line_total = sum(expected_lines, Decimal("0"))
        totals = invoice.totals
        candidates = [
            _patch(
                "MVP-LINE-001",
                "totals.line_extension_amount",
                "cac:LegalMonetaryTotal/cbc:LineExtensionAmount",
                totals.line_extension_amount,
                _money(line_total),
                "BT-106 is the sum of the deterministically recalculated BT-131 values.",
            ),
            _patch(
                "MVP-VAT-TOTAL-001",
                "vat_breakdowns[0].taxable_amount",
                "cac:TaxTotal[cac:TaxSubtotal]/cac:TaxSubtotal[1]/cbc:TaxableAmount",
                breakdown.taxable_amount,
                _money(line_total),
                "BT-116 equals the standard-rated line net sum in the frozen profile.",
            ),
        ]
        rate = _decimal(breakdown.rate)
        tax = Decimal(_money(line_total * rate / Decimal("100")))
        allowance_total = _decimal(totals.allowance_total_amount or "0")
        charge_total = _decimal(totals.charge_total_amount or "0")
        exclusive = Decimal(_money(line_total - allowance_total + charge_total))
        inclusive = Decimal(_money(exclusive + tax))
        candidates.extend(
            [
                _patch(
                    "MVP-VAT-TOTAL-001",
                    "vat_breakdowns[0].tax_amount",
                    "cac:TaxTotal[cac:TaxSubtotal]/cac:TaxSubtotal[1]/cbc:TaxAmount",
                    breakdown.tax_amount,
                    _money(tax),
                    "BT-117 is BT-116 multiplied by BT-119 and rounded to two decimals.",
                ),
                _patch(
                    "MVP-VAT-TOTAL-001",
                    "totals.tax_amount",
                    "cac:TaxTotal[not(cac:TaxSubtotal)]/cbc:TaxAmount",
                    totals.tax_amount,
                    _money(tax),
                    "BT-110 is the sum of VAT category tax amounts.",
                ),
                _patch(
                    "MVP-VAT-TOTAL-001",
                    "totals.tax_exclusive_amount",
                    "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount",
                    totals.tax_exclusive_amount,
                    _money(exclusive),
                    "BT-109 is derived from BT-106, document allowances, and document charges.",
                ),
                _patch(
                    "MVP-VAT-TOTAL-001",
                    "totals.tax_inclusive_amount",
                    "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount",
                    totals.tax_inclusive_amount,
                    _money(inclusive),
                    "BT-112 equals BT-109 plus BT-110.",
                ),
            ]
        )
        patches.extend(item for item in candidates if item is not None)
        if not patches:
            raise CorrectionSafetyError("No supported derived-value mismatch was found.")
        return tuple(patches)

    def apply(self, invoice_path: Path, proposal: CorrectionProposal, output_path: Path) -> Path:
        invoice_path = Path(invoice_path).resolve()
        output_path = Path(output_path).resolve()
        if not proposal.eligible or not proposal.patches:
            raise CorrectionSafetyError("The proposal is not eligible for automatic application.")
        if invoice_path == output_path:
            raise CorrectionSafetyError("The corrected copy must not overwrite the original invoice.")
        if output_path.exists():
            raise CorrectionSafetyError("The corrected output path already exists.")
        if _sha256(invoice_path) != proposal.source_sha256:
            raise CorrectionSafetyError("The source invoice changed after the proposal was created.")

        outcome = parse_invoice(invoice_path)
        if outcome.document is None:
            raise CorrectionSafetyError("The XML could not be parsed for correction.")
        for item in proposal.patches:
            nodes = outcome.document.getroot().xpath(item.xpath, namespaces=NS)
            if len(nodes) != 1 or not isinstance(nodes[0], etree._Element):
                raise CorrectionSafetyError(f"Correction target is not unique: {item.field}")
            current = (nodes[0].text or "").strip()
            if current != item.old_value:
                raise CorrectionSafetyError(f"Correction target changed after proposal: {item.field}")
            nodes[0].text = item.new_value

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent, delete=False
            ) as handle:
                temp_name = handle.name
                outcome.document.write(handle, encoding="utf-8", xml_declaration=True, pretty_print=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, output_path)
        finally:
            if temp_name and Path(temp_name).exists():
                Path(temp_name).unlink()
        if _sha256(invoice_path) != proposal.source_sha256:
            raise CorrectionSafetyError("Original invoice integrity changed unexpectedly.")
        return output_path


__all__ = ["CorrectionEngine", "CorrectionSafetyError", "SAFE_DERIVED_RULES"]

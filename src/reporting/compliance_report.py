from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


PASS_CONCLUSION = "Passed the selected checks implemented in this proof of concept."
FAIL_CONCLUSION = "One or more selected proof-of-concept checks require attention."
DISCLAIMER = (
    "Educational portfolio proof of concept using synthetic data and selected published requirements only. "
    "It is not affiliated with ZATCA, is not an official certification or clearance service, and does not "
    "provide legal or tax advice."
)


def _clean(value: Any, *, limit: int = 1000) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _status_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _display_basename(value: str) -> str:
    return _clean(value.replace("\\", "/").rsplit("/", 1)[-1], limit=255)


def build_compliance_report(
    analysis: dict[str, Any],
    *,
    display_filename: str,
    correction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = analysis.get("checks", [])
    proposal = analysis.get("correction_proposal") or {}
    recommendations = {
        item["rule_id"]: item for item in proposal.get("recommendations", [])
    }
    issues = []
    for issue in analysis.get("issues", []):
        recommendation = recommendations.get(issue["rule_id"], {})
        issues.append(
            {
                "rule_id": issue["rule_id"],
                "severity": issue.get("official_severity") or issue.get("internal_severity"),
                "severity_authority": "OFFICIAL" if issue.get("official_severity") else "INTERNAL_POC",
                "issue": issue.get("issue"),
                "why_flagged": issue.get("why_flagged"),
                "applicable_requirement": issue.get("applicable_requirement"),
                "official_identifiers": issue.get("official_identifiers", []),
                "sources": issue.get("sources", []),
                "suggested_action": recommendation.get("suggested_action"),
                "correction_disposition": _status_value(recommendation.get("disposition")),
                "evidence_status": issue.get("evidence_status"),
            }
        )

    after_pass = None
    revalidation = None
    if correction and correction.get("comparison"):
        comparison = correction["comparison"]
        after_pass = bool(comparison["after_selected_checks_pass"])
        revalidation = {
            "status": _status_value(correction.get("status")),
            "approval_received": bool(correction.get("approval_received")),
            "after_selected_checks_pass": after_pass,
            "resolved_rule_ids": list(comparison.get("resolved_rule_ids", [])),
            "remaining_rule_ids": list(comparison.get("remaining_rule_ids", [])),
            "introduced_rule_ids": list(comparison.get("introduced_rule_ids", [])),
            "original_preserved": bool(correction.get("original_preserved")),
        }

    selected_pass = after_pass if after_pass is not None else bool(analysis.get("selected_checks_pass"))
    return {
        "report_schema_version": "1.0.0",
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "invoice": {
            "display_filename": _display_basename(display_filename),
            "identifier": _clean(analysis.get("invoice_identifier"), limit=255) or None,
        },
        "scope": "Eight selected checks for the frozen Standard Tax Invoice proof-of-concept profile.",
        "checks_performed": [
            {
                "rule_id": check["rule_id"],
                "status": _status_value(check["status"]),
                "message": check["message"],
                "details": check.get("details", []),
            }
            for check in checks
        ],
        "passed_rule_ids": [
            check["rule_id"] for check in checks if _status_value(check["status"]) == "PASS"
        ],
        "detected_issues": issues,
        "correction_proposal": proposal or None,
        "revalidation": revalidation,
        "selected_checks_pass": selected_pass,
        "conclusion": PASS_CONCLUSION if selected_pass else FAIL_CONCLUSION,
        "limitations": analysis.get("limitations", []),
        "disclaimer": DISCLAIMER,
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    invoice = report["invoice"]
    lines = [
        "# ZATCA E-Invoicing Compliance Agent — POC Report",
        "",
        f"- Invoice file: `{_clean(invoice['display_filename'])}`",
        f"- Invoice identifier: `{_clean(invoice.get('identifier')) or 'Not available'}`",
        f"- Selected-check result: **{'PASS' if report['selected_checks_pass'] else 'ATTENTION REQUIRED'}**",
        "",
        "## Checks performed",
        "",
        "| Rule | Status | Result |",
        "| --- | --- | --- |",
    ]
    for check in report["checks_performed"]:
        lines.append(
            f"| {_clean(check['rule_id'])} | {_clean(check['status'])} | {_clean(check['message'])} |"
        )
    lines.extend(["", "## Detected issues", ""])
    if not report["detected_issues"]:
        lines.append("No issues were detected by the selected checks.")
    for issue in report["detected_issues"]:
        lines.extend(
            [
                f"### {_clean(issue['rule_id'])}",
                "",
                f"- Severity: {_clean(issue.get('severity')) or 'Not defined'} ({_clean(issue.get('severity_authority'))})",
                f"- Issue: {_clean(issue.get('issue'))}",
                f"- Why flagged: {_clean(issue.get('why_flagged'))}",
                f"- Requirement: {_clean(issue.get('applicable_requirement'))}",
                f"- Suggested action: {_clean(issue.get('suggested_action')) or 'Human review required'}",
                f"- Correction disposition: {_clean(issue.get('correction_disposition'))}",
                "- Official sources:",
            ]
        )
        for source in issue.get("sources", []):
            lines.append(
                f"  - [{_clean(source.get('title'))}]({source.get('url')}) — {_clean(source.get('section'))}"
            )
        lines.append("")
    lines.extend(["## Re-validation", ""])
    if report["revalidation"]:
        value = report["revalidation"]
        lines.extend(
            [
                f"- Status: {_clean(value['status'])}",
                f"- Original preserved: {'Yes' if value['original_preserved'] else 'No'}",
                f"- Resolved rules: {', '.join(value['resolved_rule_ids']) or 'None'}",
                f"- Remaining rules: {', '.join(value['remaining_rule_ids']) or 'None'}",
                f"- Introduced rules: {', '.join(value['introduced_rule_ids']) or 'None'}",
            ]
        )
    else:
        lines.append("No approved correction was applied in this analysis.")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            report["conclusion"],
            "",
            "## Limitations and disclaimer",
            "",
            _clean(report["disclaimer"], limit=2000),
            "",
        ]
    )
    return "\n".join(lines)

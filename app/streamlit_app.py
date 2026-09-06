from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from app.service import DemoResult, DemoService, UploadValidationError  # noqa: E402


st.set_page_config(
    page_title="ZATCA Compliance Agent — Educational POC",
    page_icon="📄",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
    .hero {padding: 1.5rem 1.7rem; border: 1px solid #dbe6e1; border-radius: 18px;
           background: linear-gradient(135deg, #f4fbf8 0%, #ffffff 75%); margin-bottom: 1rem;}
    .hero h1 {color: #123f35; margin: 0 0 .35rem 0; font-size: 2.15rem;}
    .hero p {color: #45635c; margin: 0; font-size: 1.02rem;}
    .scope-note {border-left: 4px solid #a88635; background: #fffaf0; padding: .8rem 1rem;
                 border-radius: 6px; color: #59491f; margin: .5rem 0 1.25rem;}
    div[data-testid="stMetric"] {border: 1px solid #e3e9e6; padding: .75rem; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _clear_result_state() -> None:
    for key in ("demo_result", "corrected_result", "upload_payload", "upload_name"):
        st.session_state.pop(key, None)


def _status_text(value) -> str:
    return str(getattr(value, "value", value))


def _render_result(result: DemoResult) -> None:
    analysis = result.analysis
    checks = analysis["checks"]
    passed = sum(_status_text(item["status"]) == "PASS" for item in checks)
    failed = sum(_status_text(item["status"]) == "FAIL" for item in checks)
    not_run = sum(_status_text(item["status"]) == "NOT_RUN" for item in checks)

    st.subheader("Compliance summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Selected checks", len(checks))
    col2.metric("Passed", passed)
    col3.metric("Issues", failed)
    col4.metric("Not run", not_run)
    st.progress(passed / len(checks) if checks else 0)
    if result.report["selected_checks_pass"]:
        st.success(result.report["conclusion"])
    else:
        st.warning(result.report["conclusion"])

    st.subheader("Checks performed")
    st.dataframe(
        [
            {
                "Rule": item["rule_id"],
                "Status": _status_text(item["status"]),
                "Result": item["message"],
                "Details": "; ".join(item.get("details", [])),
            }
            for item in checks
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Detected issues and official evidence")
    if not analysis["issues"]:
        st.info("No issues were detected by the selected checks.")
    recommendations = {
        item["rule_id"]: item
        for item in (analysis.get("correction_proposal") or {}).get("recommendations", [])
    }
    for issue in analysis["issues"]:
        label = f"{issue['rule_id']} · {issue.get('internal_severity') or 'Review'}"
        with st.expander(label, expanded=True):
            st.markdown("**Issue**")
            st.write(issue["issue"])
            st.markdown("**Why it was flagged**")
            st.write(issue["why_flagged"])
            st.markdown("**Applicable requirement**")
            st.write(issue.get("applicable_requirement") or "Verified evidence unavailable.")
            st.caption(
                "Official identifiers: " + ", ".join(issue.get("official_identifiers", []))
            )
            recommendation = recommendations.get(issue["rule_id"])
            if recommendation:
                st.markdown("**Suggested action**")
                st.write(recommendation["suggested_action"])
                st.caption(f"Correction disposition: {_status_text(recommendation['disposition'])}")
            st.markdown("**Official sources**")
            for source in issue.get("sources", []):
                st.markdown(f"[{source['title']}]({source['url']})")
                st.caption(
                    " · ".join(
                        part
                        for part in (source.get("version"), source.get("section"), source.get("pages"))
                        if part
                    )
                )

    proposal = analysis.get("correction_proposal")
    if proposal:
        st.subheader("Safe correction")
        if proposal["eligible"]:
            st.info(
                "A deterministic correction is available. Review every proposed change before approval."
            )
            st.dataframe(
                [
                    {
                        "Rule": item["rule_id"],
                        "Field": item["field"],
                        "Current": item["old_value"],
                        "Proposed": item["new_value"],
                        "Reason": item["rationale"],
                    }
                    for item in proposal["patches"]
                ],
                hide_index=True,
                width="stretch",
            )
            approved = st.checkbox(
                "I reviewed these deterministic changes and approve applying them to a copy.",
                key="correction_approval",
            )
            if st.button(
                "Apply to a copy and re-validate",
                type="primary",
                disabled=not approved,
                key="apply_correction",
            ):
                try:
                    with st.spinner("Applying approved changes and re-validating..."):
                        corrected = DemoService().correct_and_revalidate(
                            display_filename=st.session_state["upload_name"],
                            payload=st.session_state["upload_payload"],
                            validation_date=st.session_state["validation_date"],
                            approved=True,
                        )
                    st.session_state["corrected_result"] = corrected
                    st.rerun()
                except Exception as exc:
                    st.error(f"Correction was not applied safely: {type(exc).__name__}")
        else:
            st.warning("Automatic correction is not available. Human review is required.")
            if proposal.get("blocked_by_rule_ids"):
                st.caption("Blocked by: " + ", ".join(proposal["blocked_by_rule_ids"]))

    corrected_result = st.session_state.get("corrected_result")
    if corrected_result:
        comparison = corrected_result.correction["comparison"]
        st.subheader("Re-validation result")
        if comparison["after_selected_checks_pass"]:
            st.success("The corrected copy passed the selected proof-of-concept checks.")
        else:
            st.warning("The corrected copy still requires attention.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Resolved", len(comparison["resolved_rule_ids"]))
        col2.metric("Remaining", len(comparison["remaining_rule_ids"]))
        col3.metric("Introduced", len(comparison["introduced_rule_ids"]))
        st.caption(
            "Original preserved: "
            + ("Yes" if corrected_result.correction["original_preserved"] else "No")
        )

    download_result = corrected_result or result
    st.subheader("Download report")
    col1, col2, col3 = st.columns(3)
    col1.download_button(
        "Compliance report · JSON",
        data=download_result.report_json,
        file_name="zatca_poc_compliance_report.json",
        mime="application/json",
        on_click="ignore",
        width="stretch",
    )
    col2.download_button(
        "Compliance report · Markdown",
        data=download_result.report_markdown,
        file_name="zatca_poc_compliance_report.md",
        mime="text/markdown",
        on_click="ignore",
        width="stretch",
    )
    if corrected_result and corrected_result.corrected_xml:
        col3.download_button(
            "Corrected XML copy",
            data=corrected_result.corrected_xml,
            file_name="invoice.corrected.xml",
            mime="application/xml",
            on_click="ignore",
            width="stretch",
        )

    with st.expander("Agent tool trace"):
        st.dataframe(
            [
                {
                    "Sequence": item["sequence"],
                    "Tool": item["tool_name"],
                    "Status": _status_text(item["status"]),
                    "Error": item.get("error_type"),
                }
                for item in analysis["tool_trace"]
            ],
            hide_index=True,
            width="stretch",
        )


st.markdown(
    """
    <div class="hero">
      <h1>ZATCA E-Invoicing Compliance Agent</h1>
      <p>Evidence-grounded pre-submission checks for a synthetic Standard Tax Invoice.</p>
    </div>
    <div class="scope-note">
      Educational portfolio POC only. Use synthetic invoices—never customer or production data.
      The app runs eight selected checks and does not submit invoices to ZATCA or provide legal or tax advice.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Analysis settings")
    validation_date = st.date_input(
        "Validation date",
        value=date.today(),
        key="validation_date",
        help="Used by the deterministic issue-date check.",
    )
    st.markdown("**Frozen MVP scope**")
    st.caption("UBL 2.1 · Standard Tax Invoice · SAR · one standard-rated VAT category")
    st.markdown("**Privacy boundary**")
    st.caption("Uploaded bytes are processed in temporary local storage and are not sent to ZATCA.")

current_validation_date = validation_date.isoformat()
previous_validation_date = st.session_state.get("active_validation_date")
if previous_validation_date is not None and previous_validation_date != current_validation_date:
    _clear_result_state()
    st.session_state.pop("correction_approval", None)
st.session_state["active_validation_date"] = current_validation_date

uploaded = st.file_uploader(
    "Upload one synthetic UBL invoice",
    type=["xml"],
    accept_multiple_files=False,
    max_upload_size=2,
    help="Maximum 2 MB. The file extension is only a first filter; content is validated again by the app.",
)
synthetic_confirmed = st.checkbox(
    "I confirm this invoice is fully synthetic and contains no real customer or company data."
)

if uploaded is not None:
    payload = uploaded.getvalue()
    upload_hash = hashlib.sha256(uploaded.name.encode("utf-8") + b"\0" + payload).hexdigest()
    if st.session_state.get("active_upload_hash") != upload_hash:
        _clear_result_state()
        st.session_state["active_upload_hash"] = upload_hash
        st.session_state.pop("correction_approval", None)
    st.caption(f"Selected file: {Path(uploaded.name).name} · {len(payload):,} bytes")

analyze_clicked = st.button(
    "Analyze invoice",
    type="primary",
    disabled=uploaded is None or not synthetic_confirmed,
    width="stretch",
)
if analyze_clicked and uploaded is not None:
    try:
        with st.spinner("Running deterministic checks and retrieving verified evidence..."):
            result = DemoService().analyze(
                display_filename=uploaded.name,
                payload=payload,
                validation_date=validation_date,
            )
        st.session_state["demo_result"] = result
        st.session_state["upload_payload"] = payload
        st.session_state["upload_name"] = Path(uploaded.name).name
        st.session_state.pop("corrected_result", None)
    except UploadValidationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"The analysis could not be completed safely: {type(exc).__name__}")

if uploaded is not None and not synthetic_confirmed:
    st.info("Confirm the synthetic-data statement to enable analysis.")

stored_result = st.session_state.get("demo_result")
if stored_result:
    st.divider()
    _render_result(stored_result)

st.divider()
st.caption(
    "Not affiliated with ZATCA. No submission, clearance, reporting, signing, certification, or legal/tax guarantee is provided."
)

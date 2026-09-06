# Phase 14 — Streamlit demo

Status: **stable locally; not deployed**

## Objective

Provide a compact portfolio interface around the frozen compliance pipeline without moving validation, calculations, evidence selection, or correction decisions into the UI.

Workflow:

`Upload synthetic XML → Analyze → Summary → Checks → Issues and evidence → Suggested action → Explicit approval → Apply to copy → Re-validate → Download report`

## Files

- `app/streamlit_app.py` — presentation, session state, approval interaction, and downloads.
- `app/service.py` — testable byte-oriented boundary between uploaded content and the agent.
- `src/reporting/compliance_report.py` — structured JSON and Markdown compliance reports.
- `.streamlit/config.toml` — 2 MB upload ceiling and restrained visual theme.
- `tests/test_demo_service.py` — upload and closed-loop service tests.
- `tests/test_reporting.py` — report structure, severity labeling, and prohibited-claim tests.
- `tests/test_streamlit_app.py` — Streamlit AppTest smoke test.

## UI features

- Eight-check summary with pass, fail, and not-run counts.
- Per-check results and details.
- Evidence-grounded issue cards with official identifiers and ZATCA source links.
- Correction disposition and suggested action for every issue.
- Patch-level before/after review for eligible deterministic corrections.
- Explicit approval checkbox before the correction button is enabled.
- Re-validation comparison showing resolved, remaining, and introduced rules.
- Downloadable JSON report, Markdown report, and corrected XML copy.
- Sanitized tool trace containing tool names and statuses only.

## Safety and privacy controls

- The UI requires confirmation that the invoice is fully synthetic.
- Uploads are limited to one `.xml` file and 2 MB.
- Extension filtering is treated as a convenience, not a security boundary; the service validates size and content again.
- The uploaded filename never becomes a filesystem path. An app-controlled temporary filename is used, and the display name is reduced to a basename.
- Uploaded and corrected bytes live in temporary local storage during processing.
- No bytes are submitted to ZATCA.
- No LLM provider or API key is required by the demo.
- Changing the uploaded file or validation date invalidates stale session results.
- Corrections remain deterministic, approval-gated, source-bound, and copy-only.

## Compliance report contract

The report contains:

- invoice display name and parsed identifier;
- checks performed and passed rule IDs;
- detected issues and internal/official severity authority;
- applicable requirement, official identifiers, and source references;
- suggested action and correction disposition;
- re-validation results and original-integrity status;
- limitations, disclaimer, and bounded conclusion.

The passing conclusion is exactly:

**Passed the selected checks implemented in this proof of concept.**

## Verification

- Streamlit version: `1.63.0`.
- Demo service tests cover valid upload, invalid extension/content/size, manual-only correction, approval gating, safe correction, original preservation, and re-validation.
- Report tests verify required sections, internal severity labeling, bounded conclusion, and absence of prohibited approval claims.
- Streamlit AppTest renders the initial page without exceptions and confirms analysis is disabled before upload and synthetic-data confirmation.
- Full project suite: **140/140 passed**.
- Python bytecode compilation passed for `app`, `src`, `scripts`, `tests`, and `evaluation`.
- A headless Streamlit process reached server startup. A separate localhost health request was blocked by the execution environment, so AppTest is the authoritative UI smoke check in this phase.

The Phase 13 result remains sealed; no Final Test inference was rerun and no evaluated validator, rule, or correction policy was changed.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app/streamlit_app.py
```

## Limitations

- The interface accepts synthetic XML only for this MVP.
- The demo covers the frozen Standard Tax Invoice scenario and eight selected checks.
- It is not an official submission, clearance, reporting, signing, certification, legal, or tax service.
- The UI is intentionally simple and has not been deployed in Phase 14.

## Exit decision

Phase 14 is stable locally. Phase 15 may complete the README, repository cleanup, reproducibility commands, and GitHub presentation without changing the sealed evaluation logic.

# Phase 11 — Safe correction and re-validation

Status: **stable on Development and Validation; Final Test remains sealed**

## Objective

Add a conservative closed loop after issue detection:

1. Generate a deterministic correction proposal.
2. Require explicit human approval.
3. Apply approved patches to a new XML copy.
4. Run the same eight validators on that copy.
5. Compare failed rules before and after.

The original invoice is never overwritten. This phase does not add any legal, tax, seller, buyer, date, invoice-type, or XML content by inference.

## Correction policy

The policy is deliberately narrower than the validation scope.

| Rule | Proposal policy | Reason |
| --- | --- | --- |
| `MVP-LINE-001` | Auto-calculated only when every operand is complete, finite, and inside the frozen profile | Line net and BT-106 can be derived without business judgment |
| `MVP-VAT-TOTAL-001` | Auto-calculated only for one standard-rated breakdown with complete inputs | BT-116, BT-117, BT-109, BT-110, and BT-112 are deterministic under the frozen profile |
| `MVP-XML-001` | Human required | Repairing arbitrary XML could invent or reorder business content |
| `MVP-ID-001` | Human required | The authoritative invoice number is not inferable |
| `MVP-DATE-001` | Human required | The true commercial issue date needs confirmation |
| `MVP-TYPE-001` | Human required | Changing a legal document profile is a business decision |
| `MVP-SELLER-001` | Human required | Seller identity and VAT data require an authoritative master record |
| `MVP-BUYER-001` | Human required | Buyer identity requires an authoritative customer record |

Mixed failures are not partially auto-corrected. If any failed rule is outside the two arithmetic rules, the complete proposal is blocked. A `NOT_RUN` prerequisite also blocks automatic correction.

## Safety invariants

- The planner receives invoice XML and validator output only. It never reads dataset labels, metadata, or injection records.
- Every proposal contains the source SHA-256 and a deterministic proposal ID.
- Every patch records rule ID, canonical field, XPath, old value, new value, and calculation rationale.
- Approval is represented by an explicit `approved=True` workflow input.
- No output file is written without approval.
- An approved run requires a separate output path.
- The original path and any existing output path are rejected.
- Application fails if the source hash or any target value changed after proposal generation.
- Every XPath must resolve to exactly one existing XML element; the engine does not insert missing nodes.
- The corrected file is written atomically to a new copy and the original hash is checked again.
- Passing re-validation means only: **Passed the selected checks implemented in this proof of concept.**

## Agent and tool flow

Analysis with findings now ends with `propose_safe_correction`. Approval does not change analysis behavior.

Approved eligible flow:

`validate_invoice → retrieve_zatca_rule(s) → explain_issues → propose_safe_correction → apply_safe_correction → revalidate_invoice`

The comparison records:

- rules resolved after correction;
- rules still failing;
- newly introduced failures;
- selected-check pass state before and after.

## Files

- `src/corrections/models.py` — typed proposal, recommendation, patch, and disposition contracts.
- `src/corrections/engine.py` — deterministic calculation, safety gates, source binding, and copy writer.
- `src/tools/compliance.py` — proposal, application, and re-validation tools with sanitized audit summaries.
- `src/agent/orchestrator.py` — approval gate and closed-loop orchestration.
- `scripts/run_correction.py` — proposal-only or explicit-approval CLI.
- `scripts/audit_correction_workflow.py` — Development/Validation audit that refuses Final Test.
- `tests/test_safe_corrections.py` — safety and workflow tests.

## Verification results

Validation date: `2026-09-06`.

| Split | Cases | Eligible proposals | Approved copies tested | Re-validation passes | Proposal mismatches | Original integrity failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 48 | 9 | 9 | 9 | 0 | 0 |
| Validation | 32 | 7 | 7 | 7 | 0 | 0 |
| Total | 80 | 16 | 16 | 16 | 0 | 0 |

The eligibility decision matched the independently stored `safe_auto_correction` ground truth for all 80 allowed cases. Ground truth was used only by the audit after agent inference, not exposed to the agent.

Full project test suite: **116/116 passed**.

Analysis workflow audit after adding proposal calls:

- Development: 215 successful tool calls, zero workflow failures.
- Validation: 138 successful tool calls, zero workflow failures.
- Total: 353 successful analysis tool calls, zero workflow failures.

Python bytecode compilation completed successfully for `src`, `scripts`, and `tests`.

## CLI examples

Proposal only; no file can be written:

```bash
python3 scripts/run_correction.py INPUT.xml --validation-date 2026-09-06
```

Explicitly approved application to a new path:

```bash
python3 scripts/run_correction.py INPUT.xml \
  --validation-date 2026-09-06 \
  --approve \
  --output corrected/INPUT.corrected.xml
```

## Remaining limitations

- Correction supports only the frozen Standard Tax Invoice, SAR, single standard-rated category scenario.
- The engine does not correct missing nodes, invalid decimal source operands, malformed XML, multiple VAT categories, or business identity fields.
- The engine does not submit, clear, report, sign, or certify invoices with ZATCA.
- Development and Validation results are engineering verification, not the final unseen evaluation.
- Final Test remains untouched until Phase 13.

## Exit decision

Phase 11 is stable for its declared scope. Phase 12 may build the evaluation pipeline, but must continue to exclude Final Test until the dedicated Phase 13 run.

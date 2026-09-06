# Phase 12 — Evaluation pipeline

Status: **stable on Development and Validation; Final Test remains sealed**

## Objective

Build a repeatable evaluation layer that measures each system responsibility separately. The evaluator runs the agent with only `invoice_path` and `validation_date`, then compares predictions with separately stored ground truth. Metadata and error-injection records are not passed to the agent.

Phase 12 intentionally supports only `development` and `validation`. Any request containing `final_test`, an empty split list, or duplicate splits fails before dataset files are read.

## Metrics

### Error detection

- Micro precision, recall, and F1 over case-rule decisions.
- Macro F1 across the eight rules.
- Exact rule-set accuracy per invoice.
- Per-rule TP, FP, FN, TN, precision, recall, and F1.
- Case-level `COMPLIANT` versus `NON_COMPLIANT` confusion matrix.

### Rule retrieval

A retrieval is correct when each predicted rule has a matching issue record with the same rule ID, `VERIFIED` status, and at least one source.

### Explanation grounding

The automated contract requires:

- exact official identifiers from the verified KB record;
- exact requirement meaning from that record;
- exact source title, section, pages, and URL;
- official ZATCA source hostname;
- no prohibited approval or certification language.

This is a structural grounding metric, not a human semantic-quality judgment.

### Correction

- Eligibility precision, recall, and F1 against `safe_auto_correction` labels.
- Correction success rate for approved eligible proposals.
- Re-validation pass rate.
- Original-file integrity rate.

### Agent reliability

- Exact mandatory tool-sequence success per case.
- Evidence retrieval order compared with validator failure order.
- Total, failed, and invalid tool calls.
- Unsupported-claim rate from the grounding contract.

## Implementation

- `evaluation/metrics.py` implements binary confusion counters and safe precision/recall/F1 calculations.
- `evaluation/pipeline.py` owns split protection, isolated inference, scoring, correction trials in temporary storage, error recording, and report rendering.
- `scripts/run_evaluation.py` writes machine-readable JSON and a portfolio-friendly Markdown summary.
- `tests/test_evaluation_pipeline.py` tests imperfect metric arithmetic, split guards, aggregate reconciliation, outputs, and the inference boundary.

## Phase 12 run

Evaluation date: `2026-09-06`.

| Measure | Development + Validation |
| --- | ---: |
| Cases | 80 |
| Expected/predicted rule positives | 139 |
| Detection precision | 1.0000 |
| Detection recall | 1.0000 |
| Detection F1 | 1.0000 |
| Exact rule-set accuracy | 1.0000 |
| Rule retrieval accuracy | 1.0000 |
| Structural grounding rate | 1.0000 |
| Unsupported claims | 0 |
| Safe-correction eligibility TP / FP / FN / TN | 16 / 0 / 0 / 64 |
| Approved correction trials | 16 |
| Correction success rate | 1.0000 |
| Re-validation pass rate | 1.0000 |
| Original integrity rate | 1.0000 |
| Tool-selection success rate | 1.0000 |
| Analysis tool calls | 353 |
| Failed tool calls | 0 |
| Invalid tool calls | 0 |

The full per-rule confusion tables and case classification matrix are stored in the generated results.

Full project test suite after adding the evaluation tests: **125/125 passed**.

## Error breakdown

No Development or Validation errors were observed, so the error-record list is empty. This result is expected for a controlled synthetic benchmark whose injections are aligned to the eight deterministic validators. It does **not** demonstrate general production robustness or full ZATCA compliance.

The most important remaining risks are outside the current run:

- unseen combinations or XML structures in Final Test;
- real-world profiles beyond the frozen scope;
- human semantic assessment of explanations;
- live LLM behavior and provider failures;
- official SDK/portal behavior outside the selected checks.

## Reproduction

```bash
python3 scripts/run_evaluation.py
```

Outputs:

- `evaluation/results/phase_12_development_validation.json`
- `evaluation/results/phase_12_development_validation.md`

## Interpretation

These are engineering results used to stabilize the evaluation pipeline. They are not the final unseen evaluation and must not be described as approval, certification, or complete compliance.

The only allowed conclusion for a passing invoice remains:

**Passed the selected checks implemented in this proof of concept.**

## Exit decision

Phase 12 is stable. Phase 13 may make the one dedicated Final Test run and freeze its results; no prompt, rule, validator, correction policy, or metric implementation should be tuned after viewing that test output.

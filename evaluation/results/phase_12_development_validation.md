# Phase 12 Evaluation Results

Evaluated splits: development, validation. Final Test accessed: **No**.

## Aggregate metrics

| Metric | Result |
| --- | ---: |
| Cases | 80 |
| Detection precision | 1.0000 |
| Detection recall | 1.0000 |
| Detection F1 | 1.0000 |
| Exact rule-set accuracy | 1.0000 |
| Rule retrieval accuracy | 1.0000 |
| Explanation grounded rate | 1.0000 |
| Correction eligibility F1 | 1.0000 |
| Correction success rate | 1.0000 |
| Re-validation pass rate | 1.0000 |
| Tool-selection success rate | 1.0000 |
| Invalid tool calls | 0 |
| Unsupported claim rate | 0.0000 |

## Per-rule detection

| Rule | TP | FP | FN | TN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MVP-XML-001 | 21 | 0 | 0 | 59 | 1.0000 | 1.0000 | 1.0000 |
| MVP-ID-001 | 9 | 0 | 0 | 71 | 1.0000 | 1.0000 | 1.0000 |
| MVP-DATE-001 | 13 | 0 | 0 | 67 | 1.0000 | 1.0000 | 1.0000 |
| MVP-TYPE-001 | 13 | 0 | 0 | 67 | 1.0000 | 1.0000 | 1.0000 |
| MVP-SELLER-001 | 20 | 0 | 0 | 60 | 1.0000 | 1.0000 | 1.0000 |
| MVP-BUYER-001 | 11 | 0 | 0 | 69 | 1.0000 | 1.0000 | 1.0000 |
| MVP-LINE-001 | 21 | 0 | 0 | 59 | 1.0000 | 1.0000 | 1.0000 |
| MVP-VAT-TOTAL-001 | 31 | 0 | 0 | 49 | 1.0000 | 1.0000 | 1.0000 |

## Case classification confusion matrix

Positive class: `COMPLIANT`.

| Actual / Predicted | COMPLIANT | NON_COMPLIANT |
| --- | ---: | ---: |
| COMPLIANT | 13 | 0 |
| NON_COMPLIANT | 0 | 67 |

## Error breakdown

No errors were observed on the evaluated Development and Validation cases.

## Interpretation limits

These are engineering results on Development and Validation, not the final unseen result. The grounding metric verifies exact evidence contracts and official source linkage; it is not a substitute for human semantic review. No live LLM was evaluated in this run.

Passing means: **Passed the selected checks implemented in this proof of concept.**

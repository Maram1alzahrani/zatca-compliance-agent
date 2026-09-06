# Phase 13 Evaluation Results

Evaluated splits: final_test. Final Test accessed: **No**.

## Aggregate metrics

| Metric | Result |
| --- | ---: |
| Cases | 32 |
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
| MVP-XML-001 | 8 | 0 | 0 | 24 | 1.0000 | 1.0000 | 1.0000 |
| MVP-ID-001 | 3 | 0 | 0 | 29 | 1.0000 | 1.0000 | 1.0000 |
| MVP-DATE-001 | 5 | 0 | 0 | 27 | 1.0000 | 1.0000 | 1.0000 |
| MVP-TYPE-001 | 5 | 0 | 0 | 27 | 1.0000 | 1.0000 | 1.0000 |
| MVP-SELLER-001 | 7 | 0 | 0 | 25 | 1.0000 | 1.0000 | 1.0000 |
| MVP-BUYER-001 | 4 | 0 | 0 | 28 | 1.0000 | 1.0000 | 1.0000 |
| MVP-LINE-001 | 8 | 0 | 0 | 24 | 1.0000 | 1.0000 | 1.0000 |
| MVP-VAT-TOTAL-001 | 12 | 0 | 0 | 20 | 1.0000 | 1.0000 | 1.0000 |

## Case classification confusion matrix

Positive class: `COMPLIANT`.

| Actual / Predicted | COMPLIANT | NON_COMPLIANT |
| --- | ---: | ---: |
| COMPLIANT | 5 | 0 |
| NON_COMPLIANT | 0 | 27 |

## Error breakdown

No errors were observed on the evaluated Development and Validation cases.

## Interpretation limits

This is the frozen final unseen evaluation. No post-test tuning is permitted. The grounding metric verifies exact evidence contracts and official source linkage; it is not a substitute for human semantic review. No live LLM was evaluated in this run.

Passing means: **Passed the selected checks implemented in this proof of concept.**

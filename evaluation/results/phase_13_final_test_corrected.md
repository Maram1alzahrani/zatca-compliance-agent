# Phase 13 Final Test — Corrected Presentation View

> This file is a presentation-only companion to the immutable sealed artifacts. It does not replace or alter `phase_13_final_test.json`, `phase_13_final_test.md`, or their recorded hashes.

## Evaluation scope

- Evaluated split: `final_test`
- Final Test accessed: **Yes**
- Cases: **32**
- Data source: held-out synthetic invoices generated from the same schema, rule definitions, and mutation families used by Development and Validation
- Live LLM provider: **No**

This is an **in-distribution engineering consistency evaluation**. It is not an independent, out-of-distribution, production-compliance, semantic-RAG, or autonomous-agent benchmark.

## Aggregate results

| Metric | Result |
| --- | ---: |
| Rule-level TP / FP / FN | 52 / 0 / 0 |
| Detection precision / recall / F1 | 1.0000 / 1.0000 / 1.0000 |
| Exact rule-set accuracy | 1.0000 |
| Exact rule-evidence lookup consistency | 1.0000 |
| Structural evidence-contract consistency | 52 / 52 |
| Unsupported claims | 0 |
| Approved correction success | 7 / 7 |
| Original integrity rate | 1.0000 |
| Deterministic workflow execution success | 32 / 32 |
| Invalid or failed tool calls | 0 / 138 |

## Interpretation

The results show that the implementation behaves consistently on held-out examples from its own frozen synthetic generator family. They do **not** establish:

- agreement with the official ZATCA SDK,
- robustness to independently authored invoices,
- complete ZATCA rule coverage,
- semantic retrieval quality,
- live-LLM hallucination performance, or
- autonomous model-driven tool selection.

The strongest permitted conclusion remains:

> Passed the selected checks implemented in this proof of concept.

See `docs/external_validation_protocol.md` for the independent validation milestone required before making stronger accuracy claims.

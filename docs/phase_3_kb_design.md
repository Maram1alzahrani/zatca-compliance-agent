# Phase 3 — Traceable Knowledge Base

Status: **IMPLEMENTED AND TESTED**  
Date: 2026-09-05

## Objective

Represent the eight verified MVP checks in a machine-readable, auditable form that can later ground explanations without allowing retrieval or an LLM to replace deterministic validation.

## Files

| File | Purpose |
|---|---|
| `kb/rules/verified_mvp_rules.yaml` | Human-maintained source of truth for active rules |
| `kb/rules/unverified_and_deferred.yaml` | Quarantine for candidates that cannot affect decisions |
| `kb/schema/rule.schema.json` | Contract for a verified rule record |
| `scripts/build_kb.py` | Validates the registry and creates deterministic retrieval artifacts |
| `kb/index/retrieval_corpus.jsonl` | One self-contained retrieval chunk per active internal rule |
| `kb/index/rule_index.json` | Build provenance, registry hash, count, and policy |
| `tests/test_kb.py` | Traceability and leakage guard tests |

## Retrieval contract

Each chunk contains:

- a unique `chunk_id` tied to the internal rule ID;
- official rule/business-term identifiers;
- exact applicability for the frozen invoice profile;
- a concise meaning and deterministic validation description;
- expanded source title, version/date, section/page locator, and official URL;
- `status=VERIFIED` and `decision_eligible=true`.

No chunk contains a ground-truth label for a future synthetic invoice. The KB describes rules; the dataset will describe cases. This separation prevents label leakage.

## Authority boundary

The KB is **retrieval-only**. Later orchestration may use it to answer “why was this issue raised?” and “which official rule supports it?” It may not:

- calculate VAT or totals;
- parse or validate XML;
- decide whether a check passed;
- make an `UNVERIFIED` item decision-eligible;
- claim official ZATCA approval.

The deterministic validator must first emit an `internal_rule_id`. Retrieval then resolves that known ID to the matching chunk. Semantic search may support browsing, but it must not silently substitute a different rule for the validator's result.

## Traceability path

`validator finding → internal_rule_id → chunk_id → official identifier → source locator → official ZATCA URL`

## Change control

1. Edit the human-maintained YAML registry.
2. Keep uncertain candidates in the quarantine file.
3. Run the KB tests.
4. Rebuild the corpus and index.
5. Review the changed registry hash and chunk diff.

Generated retrieval artifacts must not be edited manually.


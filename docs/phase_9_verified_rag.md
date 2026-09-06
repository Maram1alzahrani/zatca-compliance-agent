# Phase 9 — Verified Evidence Retrieval (RAG)

Status: **STABLE**  
Date: 2026-09-06

## Objective

Provide a traceable retrieval layer that grounds later agent explanations in the eight verified MVP rules. Retrieval does not parse invoices, perform calculations, run validators, decide compliance, or modify data.

## Design decision

The corpus contains only eight rule-level chunks, and deterministic validators already return an internal rule ID. A vector database or embedding API would add latency, cost, secrets, nondeterminism, and another failure mode without improving the primary lookup path.

The MVP therefore uses two retrieval modes:

1. **Exact rule lookup** — the primary path for validator findings. A known internal rule ID maps directly to one verified evidence record.
2. **BM25-style lexical search** — a secondary path for exploratory English or Arabic queries and official identifiers.

This design can be replaced by hybrid/vector retrieval if the future corpus grows substantially, without changing the evidence contract.

## Trust boundary

The retriever loads only `kb/index/retrieval_corpus.jsonl` and enforces:

- corpus SHA-256 must match `rule_index.json`;
- policy must be retrieval-only and allow only `VERIFIED` status;
- rule count, chunk identities, and order must match the sealed index;
- every rule must be decision eligible and contain official identifiers;
- every evidence record must contain at least one source with a precise section;
- every source URL must use HTTPS on `zatca.gov.sa` or a subdomain;
- aliases must cover exactly the verified rule set and be marked `INTERNAL_RETRIEVAL_ONLY`.

Any violation stops retrieval with a structured `RetrievalError`.

## Arabic aliases

`kb/index/retrieval_aliases.yaml` contains Arabic and English search terms for retrieval convenience. These aliases are internal metadata only. They do not define, extend, translate authoritatively, or override any ZATCA requirement.

## Grounding context

`build_grounding_context` converts retrieval results into a bounded evidence packet containing:

- internal and official rule identifiers;
- exact rule meaning and applicability;
- deterministic validation logic;
- internal versus official severity fields;
- source title, version/date, section, pages, and URL;
- verification and retrieval status;
- generation restrictions.

If no verified match exists, the packet returns `NO_VERIFIED_EVIDENCE` with an empty evidence list. A later LLM must not invent a requirement or citation in that state.

## Main files

- `src/rag/models.py` — immutable evidence and retrieval contracts.
- `src/rag/retriever.py` — integrity checks, exact lookup, and lexical ranking.
- `src/rag/context.py` — bounded grounding packet for later explanation.
- `kb/index/retrieval_aliases.yaml` — internal Arabic/English search aliases.
- `scripts/query_kb.py` — retrieval-only command-line interface.
- `tests/test_rag_retrieval.py` — retrieval, security, and grounding tests.

## Verification

- Exact lookup: all **8/8** verified rules resolve to themselves.
- Curated Arabic/English unit queries: **8/8 top-1**.
- Official identifier queries: **3/3 top-1**.
- Tampered corpus: rejected.
- `UNVERIFIED` rule with recomputed checksum: rejected.
- Non-ZATCA source with recomputed checksum: rejected.
- Incomplete aliases: rejected.
- Unknown rule: zero evidence, no fallback claim.
- Final Test invoice executions: **0**.

The query set above is a unit/smoke set, not the final retrieval evaluation. Retrieval accuracy metrics and a frozen evaluation set belong to Phase 12.

## Phase boundary

Phase 9 builds retrieval and grounding only. It does not call an LLM, generate explanations, select invoice tools, apply corrections, compute evaluation metrics, or access Final Test invoices. Agent/tool orchestration begins in Phase 10.

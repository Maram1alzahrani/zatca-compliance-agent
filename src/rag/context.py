"""Construct a bounded evidence packet for later LLM explanation."""

from __future__ import annotations

from typing import Any

from src.rag.models import RetrievalResponse


def build_grounding_context(response: RetrievalResponse) -> dict[str, Any]:
    evidence = []
    for hit in response.hits:
        rule = hit.evidence
        evidence.append({
            "rank": hit.rank,
            "retrieval_score": hit.score,
            "match_method": hit.match_method,
            "internal_rule_id": rule.internal_rule_id,
            "rule_name": rule.name,
            "official_identifiers": list(rule.official_identifiers),
            "meaning": rule.meaning,
            "applicability": rule.applicability,
            "validation_logic": rule.validation_logic,
            "internal_severity": rule.internal_severity,
            "official_severity": rule.official_severity,
            "verification_status": rule.status,
            "sources": [
                {
                    "title": source.title,
                    "version": source.version,
                    "date": source.date,
                    "section": source.section,
                    "pages": source.pages,
                    "url": source.url,
                }
                for source in rule.sources
            ],
        })
    return {
        "schema_version": "1.0.0",
        "grounding_status": "VERIFIED_EVIDENCE_AVAILABLE" if evidence else "NO_VERIFIED_EVIDENCE",
        "verified_only": True,
        "retrieval_query": response.query,
        "retrieval_method": response.method,
        "generation_policy": {
            "may_explain_only_retrieved_rules": True,
            "must_preserve_source_urls_and_locators": True,
            "must_not_claim_full_or_official_compliance": True,
            "must_state_no_verified_evidence_when_empty": True,
        },
        "evidence": evidence,
    }

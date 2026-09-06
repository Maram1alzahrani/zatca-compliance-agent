"""Verified-rule retrieval for evidence grounding."""

from src.rag.context import build_grounding_context
from src.rag.models import EvidenceSource, RetrievalHit, RetrievalResponse, RuleEvidence
from src.rag.retriever import RetrievalError, VerifiedRuleRetriever

__all__ = [
    "EvidenceSource",
    "RetrievalError",
    "RetrievalHit",
    "RetrievalResponse",
    "RuleEvidence",
    "VerifiedRuleRetriever",
    "build_grounding_context",
]

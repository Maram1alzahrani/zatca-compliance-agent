"""Small-corpus verified evidence retrieval without validation side effects."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import yaml

from src.rag.models import RetrievalHit, RetrievalResponse, RuleEvidence


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "kb" / "index" / "retrieval_corpus.jsonl"
DEFAULT_INDEX = ROOT / "kb" / "index" / "rule_index.json"
DEFAULT_ALIASES = ROOT / "kb" / "index" / "retrieval_aliases.yaml"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*|[\u0600-\u06ff]+", re.IGNORECASE)
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")


class RetrievalError(ValueError):
    """Raised when verified retrieval inputs or artifacts violate their contract."""


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = ARABIC_DIACRITICS.sub("", text)
    return text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(_normalize(text))


def _trusted_zatca_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "zatca.gov.sa" or host.endswith(".zatca.gov.sa"))


class VerifiedRuleRetriever:
    def __init__(
        self,
        corpus_path: Path = DEFAULT_CORPUS,
        index_path: Path = DEFAULT_INDEX,
        aliases_path: Path = DEFAULT_ALIASES,
    ) -> None:
        corpus_bytes = corpus_path.read_bytes()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        if hashlib.sha256(corpus_bytes).hexdigest() != index.get("corpus_sha256"):
            raise RetrievalError("Retrieval corpus checksum does not match the KB index.")
        policy = index.get("policy", {})
        if policy.get("eligible_statuses") != ["VERIFIED"] or not policy.get("retrieval_only"):
            raise RetrievalError("KB index does not enforce the verified retrieval-only policy.")

        raw_records = [json.loads(line) for line in corpus_bytes.decode("utf-8").splitlines() if line.strip()]
        if len(raw_records) != index.get("rule_count"):
            raise RetrievalError("KB rule count does not match the index.")
        self._rules: dict[str, RuleEvidence] = {}
        for record in raw_records:
            evidence = RuleEvidence.from_dict(record)
            self._validate_evidence(evidence)
            if evidence.internal_rule_id in self._rules:
                raise RetrievalError(f"Duplicate verified rule: {evidence.internal_rule_id}")
            self._rules[evidence.internal_rule_id] = evidence
        if [rule.chunk_id for rule in self._rules.values()] != index.get("chunk_ids"):
            raise RetrievalError("KB chunk order or identities do not match the index.")

        alias_data = yaml.safe_load(aliases_path.read_text(encoding="utf-8"))
        if alias_data.get("authority") != "INTERNAL_RETRIEVAL_ONLY":
            raise RetrievalError("Retrieval aliases must be explicitly marked internal-only.")
        aliases = alias_data.get("aliases", {})
        if set(aliases) != set(self._rules):
            raise RetrievalError("Retrieval aliases must map exactly the verified rule set.")
        self._aliases = {rule_id: tuple(values) for rule_id, values in aliases.items()}
        self._documents = {rule_id: self._weighted_tokens(rule) for rule_id, rule in self._rules.items()}
        self._document_frequency = Counter(
            token for tokens in self._documents.values() for token in set(tokens)
        )
        self._average_length = sum(map(len, self._documents.values())) / len(self._documents)

    @staticmethod
    def _validate_evidence(evidence: RuleEvidence) -> None:
        if evidence.status != "VERIFIED" or evidence.decision_eligible is not True:
            raise RetrievalError(f"Rule is not verified and decision eligible: {evidence.internal_rule_id}")
        if evidence.chunk_id != f"rule::{evidence.internal_rule_id}":
            raise RetrievalError(f"Invalid chunk identity: {evidence.internal_rule_id}")
        if not evidence.official_identifiers or not evidence.sources:
            raise RetrievalError(f"Rule evidence is incomplete: {evidence.internal_rule_id}")
        for source in evidence.sources:
            if not source.section.strip() or not _trusted_zatca_url(source.url):
                raise RetrievalError(f"Untrusted or unlocated source in {evidence.internal_rule_id}")

    def _weighted_tokens(self, evidence: RuleEvidence) -> list[str]:
        fields = [
            evidence.retrieval_text,
            " ".join([evidence.internal_rule_id] * 6),
            " ".join(evidence.official_identifiers * 5),
            " ".join([evidence.name] * 3),
            " ".join([evidence.meaning] * 2),
            " ".join(self._aliases[evidence.internal_rule_id] * 4),
        ]
        return _tokens(" ".join(fields))

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(self._rules)

    def retrieve_rule(self, rule_id: str) -> RetrievalResponse:
        normalized = rule_id.strip().upper()
        evidence = self._rules.get(normalized)
        hits = () if evidence is None else (RetrievalHit(1, 1.0, "exact_rule_id", evidence),)
        return RetrievalResponse(rule_id, "exact_rule_id", True, hits)

    def search(self, query: str, top_k: int = 3) -> RetrievalResponse:
        if not query or not query.strip():
            raise RetrievalError("Search query must not be empty.")
        if not 1 <= top_k <= len(self._rules):
            raise RetrievalError(f"top_k must be between 1 and {len(self._rules)}.")
        query_tokens = _tokens(query)
        if not query_tokens:
            return RetrievalResponse(query, "bm25_lexical", True, ())
        query_counts = Counter(query_tokens)
        scored: list[tuple[float, str]] = []
        total_docs = len(self._documents)
        for rule_id, tokens in self._documents.items():
            frequencies = Counter(tokens)
            doc_length = len(tokens)
            score = 0.0
            for token, query_frequency in query_counts.items():
                frequency = frequencies.get(token, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequency[token]
                inverse_frequency = math.log(1 + (total_docs - document_frequency + 0.5) / (document_frequency + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * doc_length / self._average_length)
                score += inverse_frequency * (frequency * 2.5 / denominator) * query_frequency
            if score > 0:
                scored.append((score, rule_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        hits = tuple(
            RetrievalHit(rank, round(score, 8), "bm25_lexical", self._rules[rule_id])
            for rank, (score, rule_id) in enumerate(scored[:top_k], start=1)
        )
        return RetrievalResponse(query, "bm25_lexical", True, hits)

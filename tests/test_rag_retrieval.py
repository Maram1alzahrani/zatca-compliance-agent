from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from src.rag import RetrievalError, VerifiedRuleRetriever, build_grounding_context


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "kb" / "index" / "retrieval_corpus.jsonl"
INDEX = ROOT / "kb" / "index" / "rule_index.json"
ALIASES = ROOT / "kb" / "index" / "retrieval_aliases.yaml"
RULE_IDS = (
    "MVP-BUYER-001",
    "MVP-DATE-001",
    "MVP-ID-001",
    "MVP-LINE-001",
    "MVP-SELLER-001",
    "MVP-TYPE-001",
    "MVP-VAT-TOTAL-001",
    "MVP-XML-001",
)


class VerifiedRuleRetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retriever = VerifiedRuleRetriever()

    def test_corpus_exposes_exactly_eight_verified_rules(self) -> None:
        self.assertEqual(RULE_IDS, self.retriever.rule_ids)

    def test_exact_rule_id_returns_one_verified_hit_for_every_rule(self) -> None:
        for rule_id in RULE_IDS:
            with self.subTest(rule_id=rule_id):
                response = self.retriever.retrieve_rule(rule_id.lower())
                self.assertTrue(response.verified_only)
                self.assertEqual("exact_rule_id", response.method)
                self.assertEqual(1, len(response.hits))
                self.assertEqual(rule_id, response.hits[0].evidence.internal_rule_id)
                self.assertEqual("VERIFIED", response.hits[0].evidence.status)

    def test_unknown_rule_id_returns_no_evidence(self) -> None:
        self.assertEqual((), self.retriever.retrieve_rule("MVP-NOT-REAL").hits)

    def test_english_and_arabic_queries_rank_expected_rule_first(self) -> None:
        queries = {
            "MVP-XML-001": "UBL XSD schema malformed XML",
            "MVP-ID-001": "missing invoice number BT-1",
            "MVP-DATE-001": "future invoice issue date YYYY-MM-DD",
            "MVP-TYPE-001": "invoice subtype transaction code 388",
            "MVP-SELLER-001": "الرقم الضريبي للبائع",
            "MVP-BUYER-001": "اسم المشتري مفقود",
            "MVP-LINE-001": "BT-106 invoice line net sum",
            "MVP-VAT-TOTAL-001": "المبلغ الخاضع لضريبة القيمة المضافة والاجمالي شامل الضريبة",
        }
        for expected, query in queries.items():
            with self.subTest(query=query):
                response = self.retriever.search(query, top_k=3)
                self.assertTrue(response.hits)
                self.assertEqual(expected, response.hits[0].evidence.internal_rule_id)

    def test_official_identifier_is_retrievable(self) -> None:
        cases = {"BR-KSA-42": "MVP-BUYER-001", "BR-CO-10": "MVP-LINE-001", "BR-S-09": "MVP-VAT-TOTAL-001"}
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(expected, self.retriever.search(query, 1).hits[0].evidence.internal_rule_id)

    def test_unrelated_query_returns_no_hit(self) -> None:
        self.assertEqual((), self.retriever.search("طقس جدة غدا", 3).hits)

    def test_empty_query_and_invalid_top_k_are_rejected(self) -> None:
        for query in ("", "   "):
            with self.subTest(query=query), self.assertRaises(RetrievalError):
                self.retriever.search(query)
        for value in (0, 9):
            with self.subTest(top_k=value), self.assertRaises(RetrievalError):
                self.retriever.search("invoice", value)

    def test_evidence_contains_precise_trusted_sources(self) -> None:
        for rule_id in RULE_IDS:
            evidence = self.retriever.retrieve_rule(rule_id).hits[0].evidence
            self.assertTrue(evidence.official_identifiers)
            self.assertTrue(evidence.meaning)
            self.assertTrue(evidence.validation_logic)
            self.assertTrue(evidence.sources)
            for source in evidence.sources:
                self.assertTrue(source.section.strip())
                self.assertTrue(source.url.startswith("https://zatca.gov.sa/"))

    def test_response_is_json_serializable_without_custom_encoder(self) -> None:
        response = self.retriever.retrieve_rule("MVP-ID-001")
        encoded = json.dumps(response.to_dict(), ensure_ascii=False)
        self.assertIn("BR-02", encoded)

    def test_grounding_context_contains_only_retrieved_verified_evidence(self) -> None:
        response = self.retriever.retrieve_rule("MVP-ID-001")
        context = build_grounding_context(response)
        self.assertEqual("VERIFIED_EVIDENCE_AVAILABLE", context["grounding_status"])
        self.assertEqual(1, len(context["evidence"]))
        self.assertEqual("MVP-ID-001", context["evidence"][0]["internal_rule_id"])
        self.assertEqual("VERIFIED", context["evidence"][0]["verification_status"])
        self.assertTrue(context["evidence"][0]["sources"])

    def test_empty_retrieval_context_explicitly_forbids_unsupported_grounding(self) -> None:
        context = build_grounding_context(self.retriever.retrieve_rule("MVP-NOT-REAL"))
        self.assertEqual("NO_VERIFIED_EVIDENCE", context["grounding_status"])
        self.assertEqual([], context["evidence"])
        self.assertTrue(context["generation_policy"]["must_state_no_verified_evidence_when_empty"])

    def test_corpus_tampering_is_rejected_by_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.jsonl"
            corpus.write_bytes(CORPUS.read_bytes() + b"\n")
            index = root / "index.json"
            index.write_bytes(INDEX.read_bytes())
            with self.assertRaises(RetrievalError):
                VerifiedRuleRetriever(corpus, index, ALIASES)

    def test_unverified_rule_is_rejected_even_with_matching_checksum(self) -> None:
        self._assert_modified_corpus_rejected(lambda records: records[0].update(status="UNVERIFIED"))

    def test_non_zatca_source_is_rejected_even_with_matching_checksum(self) -> None:
        self._assert_modified_corpus_rejected(
            lambda records: records[0]["sources"][0].update(url="https://example.com/not-official.pdf")
        )

    def test_alias_file_must_cover_exact_verified_rule_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            aliases = yaml.safe_load(ALIASES.read_text(encoding="utf-8"))
            aliases["aliases"].pop("MVP-ID-001")
            path = Path(directory) / "aliases.yaml"
            path.write_text(yaml.safe_dump(aliases), encoding="utf-8")
            with self.assertRaises(RetrievalError):
                VerifiedRuleRetriever(CORPUS, INDEX, path)

    def _assert_modified_corpus_rejected(self, mutate) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines()]
            mutate(records)
            payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records).encode("utf-8")
            corpus = root / "corpus.jsonl"
            corpus.write_bytes(payload)
            index_data = json.loads(INDEX.read_text(encoding="utf-8"))
            index_data["corpus_sha256"] = hashlib.sha256(payload).hexdigest()
            index = root / "index.json"
            index.write_text(json.dumps(index_data), encoding="utf-8")
            with self.assertRaises(RetrievalError):
                VerifiedRuleRetriever(corpus, index, ALIASES)


if __name__ == "__main__":
    unittest.main()

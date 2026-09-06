from __future__ import annotations

import json
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.build_kb import KnowledgeBaseError, build, load_registry, validate_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "kb" / "rules" / "verified_mvp_rules.yaml"
DEFERRED = ROOT / "kb" / "rules" / "unverified_and_deferred.yaml"
SCHEMA = ROOT / "kb" / "schema" / "rule.schema.json"


class KnowledgeBaseTests(unittest.TestCase):
    def test_active_registry_is_valid_and_has_eight_unique_rules(self) -> None:
        registry = load_registry(REGISTRY)
        validate_registry(registry)
        ids = [rule["internal_rule_id"] for rule in registry["rules"]]
        self.assertEqual(8, len(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_reference_resolves_to_an_official_source(self) -> None:
        registry = load_registry(REGISTRY)
        for rule in registry["rules"]:
            for reference in rule["source_references"]:
                source = registry["sources"][reference["source"]]
                self.assertIn("zatca.gov.sa", source["url"])
                self.assertTrue(reference["section"].strip())

    def test_rules_match_the_declared_contract(self) -> None:
        registry = load_registry(REGISTRY)
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        required = set(schema["required"])
        allowed = set(schema["properties"])
        pattern = re.compile(schema["properties"]["internal_rule_id"]["pattern"])
        for rule in registry["rules"]:
            self.assertEqual(required, set(rule), rule["internal_rule_id"])
            self.assertTrue(set(rule).issubset(allowed))
            self.assertIsNotNone(pattern.fullmatch(rule["internal_rule_id"]))
            self.assertIn(
                rule["internal_severity"],
                schema["properties"]["internal_severity"]["enum"],
            )

    def test_unverified_and_deferred_items_cannot_enter_corpus(self) -> None:
        blocked = yaml.safe_load(DEFERRED.read_text(encoding="utf-8"))["items"]
        blocked_names = {item["candidate"] for item in blocked}
        with tempfile.TemporaryDirectory() as tmp:
            corpus_path, _ = build(REGISTRY, Path(tmp))
            chunks = [json.loads(line) for line in corpus_path.read_text().splitlines()]
        self.assertTrue(all(chunk["decision_eligible"] for chunk in chunks))
        self.assertTrue(all(chunk["status"] == "VERIFIED" for chunk in chunks))
        self.assertTrue(blocked_names.isdisjoint({chunk["name"] for chunk in chunks}))

    def test_builder_rejects_non_verified_rule(self) -> None:
        registry = load_registry(REGISTRY)
        registry["rules"][0]["status"] = "UNVERIFIED"
        with self.assertRaises(KnowledgeBaseError):
            validate_registry(registry)

    def test_generated_index_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = build(REGISTRY, Path(first))
            second_paths = build(REGISTRY, Path(second))
            for left, right in zip(first_paths, second_paths):
                self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_index_seals_the_generated_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corpus_path, index_path = build(REGISTRY, Path(tmp))
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(hashlib.sha256(corpus_path.read_bytes()).hexdigest(), index["corpus_sha256"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Build the retrieval-only knowledge-base index from verified rule records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "kb" / "rules" / "verified_mvp_rules.yaml"
DEFAULT_INDEX_DIR = ROOT / "kb" / "index"


class KnowledgeBaseError(ValueError):
    """Raised when a rule registry violates the Phase 3 contract."""


def load_registry(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise KnowledgeBaseError("Registry root must be a mapping")
    return data


def validate_registry(registry: dict[str, Any]) -> None:
    sources = registry.get("sources")
    rules = registry.get("rules")
    if not isinstance(sources, dict) or not sources:
        raise KnowledgeBaseError("At least one source is required")
    if not isinstance(rules, list) or not rules:
        raise KnowledgeBaseError("At least one rule is required")

    required = {
        "internal_rule_id",
        "status",
        "name",
        "official_identifiers",
        "meaning",
        "applicable_invoice_type",
        "validation_logic",
        "internal_severity",
        "official_severity",
        "source_references",
        "valid_example",
        "invalid_example",
    }
    seen_ids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise KnowledgeBaseError("Every rule must be a mapping")
        missing = required - rule.keys()
        if missing:
            raise KnowledgeBaseError(
                f"{rule.get('internal_rule_id', '<unknown>')} missing {sorted(missing)}"
            )
        rule_id = rule["internal_rule_id"]
        if rule_id in seen_ids:
            raise KnowledgeBaseError(f"Duplicate rule ID: {rule_id}")
        seen_ids.add(rule_id)
        if rule["status"] != "VERIFIED":
            raise KnowledgeBaseError(f"Non-verified rule in active registry: {rule_id}")
        if not rule["official_identifiers"]:
            raise KnowledgeBaseError(f"Official identifiers missing: {rule_id}")
        if not rule["source_references"]:
            raise KnowledgeBaseError(f"Source reference missing: {rule_id}")
        for reference in rule["source_references"]:
            if reference.get("source") not in sources:
                raise KnowledgeBaseError(
                    f"Unknown source {reference.get('source')!r} in {rule_id}"
                )


def make_chunk(rule: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    expanded_sources = []
    locator_text = []
    for ref in rule["source_references"]:
        source = sources[ref["source"]]
        expanded = {
            "source_key": ref["source"],
            "title": source["title"],
            "version": source.get("version"),
            "date": source.get("date"),
            "section": ref["section"],
            "pages": ref.get("pages"),
            "url": source["url"],
        }
        expanded_sources.append(expanded)
        locator_text.append(
            f"{source['title']} | {ref['section']} | {ref.get('pages', 'no page')}"
        )

    retrieval_text = "\n".join(
        [
            f"Rule: {rule['internal_rule_id']} — {rule['name']}",
            f"Official identifiers: {', '.join(rule['official_identifiers'])}",
            f"Meaning: {rule['meaning']}",
            f"Applies to: {rule['applicable_invoice_type']}",
            "Evidence locations: " + "; ".join(locator_text),
            f"Valid example: {rule['valid_example']}",
            f"Invalid example: {rule['invalid_example']}",
        ]
    )
    return {
        "chunk_id": f"rule::{rule['internal_rule_id']}",
        "internal_rule_id": rule["internal_rule_id"],
        "status": "VERIFIED",
        "decision_eligible": True,
        "name": rule["name"],
        "official_identifiers": rule["official_identifiers"],
        "applicability": rule["applicable_invoice_type"],
        "internal_severity": rule["internal_severity"],
        "official_severity": rule["official_severity"],
        "meaning": rule["meaning"],
        "validation_logic": rule["validation_logic"],
        "sources": expanded_sources,
        "retrieval_text": retrieval_text,
    }


def build(registry_path: Path, output_dir: Path) -> tuple[Path, Path]:
    registry_bytes = registry_path.read_bytes()
    registry = load_registry(registry_path)
    validate_registry(registry)
    chunks = [make_chunk(rule, registry["sources"]) for rule in registry["rules"]]
    chunks.sort(key=lambda item: item["internal_rule_id"])

    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / "retrieval_corpus.jsonl"
    index_path = output_dir / "rule_index.json"
    corpus_bytes = "".join(
        json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n" for chunk in chunks
    ).encode("utf-8")
    corpus_path.write_bytes(corpus_bytes)
    index = {
        "kb_version": registry["registry_version"],
        "built_from": str(registry_path.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "rule_count": len(chunks),
        "chunk_ids": [chunk["chunk_id"] for chunk in chunks],
        "policy": {
            "retrieval_only": True,
            "deterministic_validation_required": True,
            "eligible_statuses": ["VERIFIED"],
        },
    }
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return corpus_path, index_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_INDEX_DIR)
    args = parser.parse_args()
    corpus, index = build(args.registry, args.output_dir)
    print(f"Built {corpus}")
    print(f"Built {index}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.audit_scaled_dataset import audit
from scripts.generate_scaled_dataset import RULE_ORDER, SPLITS, generate


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
V1 = DATA / "synthetic" / "v1"
TRUTH = DATA / "ground_truth" / "v1"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ScaledSyntheticDatasetTests(unittest.TestCase):
    def test_split_sizes_and_case_ids_are_disjoint(self) -> None:
        groups = []
        for split, settings in SPLITS.items():
            manifest = json.loads((V1 / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["count"], manifest["case_count"])
            self.assertEqual(settings["count"], len(manifest["cases"]))
            groups.append({case["case_id"] for case in manifest["cases"]})
        for left_index, left in enumerate(groups):
            for right in groups[left_index + 1:]:
                self.assertTrue(left.isdisjoint(right))

    def test_four_data_planes_are_separate_and_aligned(self) -> None:
        forbidden_metadata = {"expected_rule_ids", "expected_issue_count", "safe_auto_correction", "injections", "error_type"}
        for split in SPLITS:
            manifest = json.loads((V1 / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
            metadata = read_jsonl(V1 / "metadata" / f"{split}.jsonl")
            truth = read_jsonl(TRUTH / f"{split}.jsonl")
            injections = read_jsonl(V1 / "error_injections" / f"{split}.jsonl")
            groups = [
                {case["case_id"] for case in manifest["cases"]},
                {record["case_id"] for record in metadata},
                {record["case_id"] for record in truth},
                {record["case_id"] for record in injections},
            ]
            self.assertTrue(all(group == groups[0] for group in groups[1:]))
            self.assertTrue(all(forbidden_metadata.isdisjoint(record) for record in metadata))
            self.assertTrue(all("expected_rule_ids" not in case for case in manifest["cases"]))

    def test_invoice_names_and_payloads_do_not_reveal_labels(self) -> None:
        forbidden = (b"MVP-", b"COMPLIANT", b"MISSING_FIELD", b"INVALID_FORMAT", b"VAT_ERROR", b"TOTAL_MISMATCH")
        for split in SPLITS:
            manifest = json.loads((V1 / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
            expected_names = [f"invoice_{index:04d}.xml" for index in range(1, len(manifest["cases"]) + 1)]
            self.assertEqual(expected_names, [Path(case["invoice_file"]).name for case in manifest["cases"]])
            for case in manifest["cases"]:
                payload = (DATA / case["invoice_file"]).read_bytes()
                self.assertTrue(all(token not in payload for token in forbidden))

    def test_manifest_hashes_match_and_invoice_bytes_do_not_cross_splits(self) -> None:
        hashes_by_split = []
        for split in SPLITS:
            manifest = json.loads((V1 / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
            split_hashes = set()
            for case in manifest["cases"]:
                digest = sha256(DATA / case["invoice_file"])
                self.assertEqual(case["sha256"], digest)
                split_hashes.add(digest)
            self.assertEqual(len(manifest["cases"]), len(split_hashes))
            hashes_by_split.append(split_hashes)
        for left_index, left in enumerate(hashes_by_split):
            for right in hashes_by_split[left_index + 1:]:
                self.assertTrue(left.isdisjoint(right))

    def test_every_split_covers_every_active_rule_and_has_mixed_cases(self) -> None:
        for split, settings in SPLITS.items():
            truth = read_jsonl(TRUTH / f"{split}.jsonl")
            injections = read_jsonl(V1 / "error_injections" / f"{split}.jsonl")
            covered = {rule for record in truth for rule in record["expected_rule_ids"]}
            self.assertEqual(set(RULE_ORDER), covered)
            self.assertEqual(settings["compliant"], sum(record["expected_selected_checks_pass"] for record in truth))
            self.assertTrue(any(record["injection_count"] > 1 for record in injections))

    def test_injection_records_contain_before_after_and_expected_values(self) -> None:
        for split in SPLITS:
            records = read_jsonl(V1 / "error_injections" / f"{split}.jsonl")
            for record in records:
                self.assertEqual(record["injection_applied"], bool(record["injections"]))
                self.assertEqual(record["injection_count"], len(record["injections"]))
                for injection in record["injections"]:
                    self.assertIn("target_field", injection)
                    self.assertIn("before", injection)
                    self.assertIn("after", injection)
                    self.assertIn("expected_value", injection)
                    self.assertTrue(injection["rule_ids"])

    def test_malformed_counts_match_declared_operator(self) -> None:
        for split in SPLITS:
            manifest = json.loads((V1 / "manifests" / f"{split}.json").read_text(encoding="utf-8"))
            injection_by_id = {record["case_id"]: record for record in read_jsonl(V1 / "error_injections" / f"{split}.jsonl")}
            malformed = set()
            declared = set()
            for case in manifest["cases"]:
                if any(item["operator"] == "malformed_xml" for item in injection_by_id[case["case_id"]]["injections"]):
                    declared.add(case["case_id"])
                try:
                    ET.fromstring((DATA / case["invoice_file"]).read_bytes())
                except ET.ParseError:
                    malformed.add(case["case_id"])
            self.assertEqual(declared, malformed)

    def test_final_test_seal_matches_all_control_files(self) -> None:
        seal = json.loads((V1 / "final_test_seal.json").read_text(encoding="utf-8"))
        self.assertTrue(seal["sealed_before_evaluation"])
        for item in seal["files"].values():
            self.assertEqual(item["sha256"], sha256(DATA / item["path"]))

    def test_phase_8_audit_refuses_final_test(self) -> None:
        with self.assertRaises(ValueError):
            audit(DATA, ("final_test",))

    def test_generation_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            other_data = Path(directory) / "data"
            generate(other_data)
            expected = sorted(path.relative_to(DATA) for path in (DATA / "synthetic" / "v1").rglob("*") if path.is_file())
            expected += sorted(path.relative_to(DATA) for path in TRUTH.rglob("*") if path.is_file())
            actual = sorted(path.relative_to(other_data) for path in (other_data / "synthetic" / "v1").rglob("*") if path.is_file())
            actual += sorted(path.relative_to(other_data) for path in (other_data / "ground_truth" / "v1").rglob("*") if path.is_file())
            self.assertEqual(sorted(expected), sorted(actual))
            for relative in expected:
                self.assertEqual((DATA / relative).read_bytes(), (other_data / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()

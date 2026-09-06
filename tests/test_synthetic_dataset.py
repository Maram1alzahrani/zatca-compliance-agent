from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.generate_synthetic_dataset import CASES, generate


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class SyntheticDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        generate(DATA)
        cls.manifest = json.loads((DATA / "synthetic/manifests/dev_manifest.json").read_text())
        cls.metadata = read_jsonl(DATA / "synthetic/metadata/dev.jsonl")
        cls.truth = read_jsonl(DATA / "ground_truth/dev.jsonl")
        cls.injections = read_jsonl(DATA / "synthetic/error_injections/dev.jsonl")

    def test_small_development_split_has_neutral_file_names(self) -> None:
        self.assertEqual(12, self.manifest["case_count"])
        names = [Path(case["invoice_file"]).name for case in self.manifest["cases"]]
        self.assertEqual([f"inv_{i:04d}.xml" for i in range(1, 13)], names)
        forbidden = ("compliant", "missing", "invalid", "vat", "error", "mismatch")
        self.assertTrue(all(not any(token in name.lower() for token in forbidden) for name in names))

    def test_data_planes_are_separate_and_aligned(self) -> None:
        ids = [{record["case_id"] for record in records} for records in (self.metadata, self.truth, self.injections)]
        self.assertTrue(all(group == ids[0] for group in ids[1:]))
        self.assertEqual({case.case_id for case in CASES}, ids[0])
        self.assertTrue(all("expected_rule_ids" not in record for record in self.metadata))
        self.assertTrue(all("primary_error_type" not in record for record in self.metadata))

    def test_manifest_hashes_match_invoice_bytes(self) -> None:
        for case in self.manifest["cases"]:
            payload = (DATA / case["invoice_file"]).read_bytes()
            self.assertEqual(case["sha256"], hashlib.sha256(payload).hexdigest())

    def test_only_the_deliberate_xml_case_is_not_well_formed(self) -> None:
        malformed_ids = set()
        for case in self.manifest["cases"]:
            try:
                ET.fromstring((DATA / case["invoice_file"]).read_bytes())
            except ET.ParseError:
                malformed_ids.add(case["case_id"])
        self.assertEqual({"C0002"}, malformed_ids)

    def test_ground_truth_covers_all_active_rules(self) -> None:
        covered = {rule_id for record in self.truth for rule_id in record["expected_rule_ids"]}
        self.assertEqual(
            {
                "MVP-XML-001", "MVP-ID-001", "MVP-DATE-001", "MVP-TYPE-001",
                "MVP-SELLER-001", "MVP-BUYER-001", "MVP-LINE-001", "MVP-VAT-TOTAL-001",
            },
            covered,
        )
        self.assertEqual(1, sum(record["expected_selected_checks_pass"] for record in self.truth))

    def test_every_fault_case_has_one_declared_injection(self) -> None:
        by_id = {record["case_id"]: record for record in self.injections}
        for truth in self.truth:
            expected = not truth["expected_selected_checks_pass"]
            self.assertEqual(expected, by_id[truth["case_id"]]["injection_applied"])

    def test_generation_is_byte_for_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "data"
            generate(other)
            expected_files = sorted(
                [path.relative_to(DATA) for path in (DATA / "synthetic/dev/invoices").glob("*.xml")]
                + [
                    Path("synthetic/metadata/dev.jsonl"),
                    Path("synthetic/error_injections/dev.jsonl"),
                    Path("synthetic/manifests/dev_manifest.json"),
                    Path("ground_truth/dev.jsonl"),
                ]
            )
            actual_files = sorted(path.relative_to(other) for path in other.rglob("*") if path.is_file())
            self.assertEqual(expected_files, actual_files)
            for relative in expected_files:
                self.assertEqual((DATA / relative).read_bytes(), (other / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.final_evaluation import (
    FinalEvaluationRunner,
    build_code_freeze,
    verify_final_dataset_seal,
)
from evaluation.pipeline import EvaluationRunner


ROOT = Path(__file__).resolve().parents[1]


class FinalEvaluationGuardTests(unittest.TestCase):
    def test_phase_12_still_refuses_final_test(self) -> None:
        with self.assertRaises(ValueError):
            EvaluationRunner(ROOT / "data").evaluate(("final_test",))

    def test_final_dataset_seal_verifies_before_evaluation(self) -> None:
        result = verify_final_dataset_seal(ROOT / "data")
        self.assertEqual(32, result["case_count"])
        self.assertEqual(4, result["control_files_verified"])
        self.assertEqual(32, result["invoice_files_verified"])

    def test_code_freeze_covers_runtime_kb_schema_and_final_seal(self) -> None:
        freeze = build_code_freeze(ROOT)
        paths = {item["path"] for item in freeze["files"]}
        self.assertIn("evaluation/final_evaluation.py", paths)
        self.assertIn("evaluation/pipeline.py", paths)
        self.assertIn("src/agent/orchestrator.py", paths)
        self.assertIn("kb/rules/verified_mvp_rules.yaml", paths)
        self.assertIn("data/synthetic/v1/final_test_seal.json", paths)
        self.assertTrue(freeze["aggregate_sha256"])

    def test_existing_run_artifact_blocks_before_dataset_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "phase_13_final_run_state.json").write_text(
                json.dumps({"status": "COMPLETED"}), encoding="utf-8"
            )
            runner = FinalEvaluationRunner(Path("/project/does/not/exist"), output_dir=output)
            with self.assertRaises(RuntimeError):
                runner.run()


if __name__ == "__main__":
    unittest.main()

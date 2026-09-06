from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.metrics import BinaryCounter, precision_recall_f1
from evaluation.pipeline import EvaluationRunner, write_results
from src.validators.checks import RULE_IDS


ROOT = Path(__file__).resolve().parents[1]


class EvaluationMetricUnitTests(unittest.TestCase):
    def test_precision_recall_f1_handles_imperfect_and_zero_cases(self) -> None:
        result = precision_recall_f1(3, 1, 2)
        self.assertAlmostEqual(0.75, result["precision"])
        self.assertAlmostEqual(0.6, result["recall"])
        self.assertAlmostEqual(2 / 3, result["f1"])
        self.assertEqual(
            {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            precision_recall_f1(0, 0, 0),
        )

    def test_binary_counter_tracks_all_confusion_cells(self) -> None:
        counter = BinaryCounter()
        for expected, predicted in ((True, True), (False, True), (True, False), (False, False)):
            counter.update(expected, predicted)
        result = counter.to_dict()
        self.assertEqual((1, 1, 1, 1), (result["tp"], result["fp"], result["fn"], result["tn"]))


class EvaluationPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = EvaluationRunner(ROOT / "data").evaluate()

    def test_final_test_is_explicitly_refused_before_data_access(self) -> None:
        with self.assertRaises(ValueError):
            EvaluationRunner(Path("/path/that/does/not/exist")).evaluate(("final_test",))

    def test_duplicate_or_empty_splits_are_refused(self) -> None:
        runner = EvaluationRunner(ROOT / "data")
        with self.assertRaises(ValueError):
            runner.evaluate(())
        with self.assertRaises(ValueError):
            runner.evaluate(("validation", "validation"))

    def test_aggregate_counts_and_detection_metrics_are_exact(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(80, aggregate["case_count"])
        self.assertEqual(139, aggregate["error_detection"]["micro"]["tp"])
        self.assertEqual(0, aggregate["error_detection"]["micro"]["fp"])
        self.assertEqual(0, aggregate["error_detection"]["micro"]["fn"])
        self.assertEqual(1.0, aggregate["error_detection"]["micro"]["f1"])
        self.assertEqual(set(RULE_IDS), set(aggregate["error_detection"]["per_rule"]))
        self.assertTrue(
            all(metric["support_positive"] > 0 for metric in aggregate["error_detection"]["per_rule"].values())
        )

    def test_retrieval_grounding_correction_and_reliability_are_separate(self) -> None:
        aggregate = self.result["aggregate"]
        self.assertEqual(139, aggregate["rule_retrieval"]["predicted_issues_evaluated"])
        self.assertEqual(1.0, aggregate["rule_retrieval"]["accuracy"])
        self.assertEqual(1.0, aggregate["explanation_grounding"]["grounded_rate"])
        self.assertEqual(0, aggregate["explanation_grounding"]["unsupported_claim_count"])
        self.assertEqual(16, aggregate["correction"]["approved_attempts"])
        self.assertEqual(1.0, aggregate["correction"]["correction_success_rate"])
        self.assertEqual(1.0, aggregate["correction"]["revalidation_pass_rate"])
        self.assertEqual(353, aggregate["agent_reliability"]["tool_calls"])
        self.assertEqual(0, aggregate["agent_reliability"]["invalid_tool_calls"])

    def test_evaluation_declares_inference_boundary_and_no_llm(self) -> None:
        self.assertFalse(self.result["final_test_accessed"])
        self.assertEqual(["invoice_path", "validation_date"], self.result["agent_input_contract"])
        self.assertIsNone(self.result["llm_provider"])

    def test_split_totals_reconcile_with_aggregate(self) -> None:
        split_total = sum(item["case_count"] for item in self.result["split_results"].values())
        split_calls = sum(
            item["agent_reliability"]["tool_calls"] for item in self.result["split_results"].values()
        )
        self.assertEqual(self.result["aggregate"]["case_count"], split_total)
        self.assertEqual(self.result["aggregate"]["agent_reliability"]["tool_calls"], split_calls)

    def test_json_and_markdown_reports_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path, markdown_path = write_results(self.result, Path(directory))
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertEqual(80, parsed["aggregate"]["case_count"])
            self.assertIn("Case classification confusion matrix", markdown)
            self.assertIn("Passed the selected checks implemented in this proof of concept.", markdown)


if __name__ == "__main__":
    unittest.main()

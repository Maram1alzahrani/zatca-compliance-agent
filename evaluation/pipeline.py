from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.parse import urlparse

from src.agent import ComplianceAgent, CorrectionWorkflowStatus
from src.agent.explainers import BANNED_CLAIMS
from src.tools import ToolCallStatus
from src.validators import CheckStatus
from src.validators.checks import RULE_IDS

from evaluation.metrics import BinaryCounter, precision_recall_f1, safe_divide


ALLOWED_PHASE_12_SPLITS = ("development", "validation")
EVALUATION_DATE = date(2026, 9, 6)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> dict[str, dict]:
    return {
        item["case_id"]: item
        for item in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    }


def _is_official_zatca_url(value: str) -> bool:
    host = (urlparse(value).hostname or "").lower()
    return host == "zatca.gov.sa" or host.endswith(".zatca.gov.sa")


class _Accumulator:
    def __init__(self) -> None:
        self.cases = 0
        self.exact_matches = 0
        self.rules = {rule_id: BinaryCounter() for rule_id in RULE_IDS}
        self.compliance = BinaryCounter()
        self.retrieval_total = 0
        self.retrieval_correct = 0
        self.grounding_total = 0
        self.grounding_supported = 0
        self.unsupported_claims = 0
        self.correction = BinaryCounter()
        self.correction_attempts = 0
        self.correction_successes = 0
        self.revalidation_passes = 0
        self.original_integrity_passes = 0
        self.tool_selection_successes = 0
        self.tool_calls = 0
        self.failed_tool_calls = 0
        self.invalid_tool_calls = 0
        self.errors: list[dict] = []
        self.error_counts: Counter[str] = Counter()

    def error(self, category: str, split: str, case_id: str, details: dict) -> None:
        self.error_counts[category] += 1
        self.errors.append({"category": category, "split": split, "case_id": case_id, **details})

    def finalize(self) -> dict:
        per_rule = {rule_id: counter.to_dict() for rule_id, counter in self.rules.items()}
        tp = sum(counter.tp for counter in self.rules.values())
        fp = sum(counter.fp for counter in self.rules.values())
        fn = sum(counter.fn for counter in self.rules.values())
        macro_f1 = safe_divide(sum(item["f1"] for item in per_rule.values()), len(per_rule))
        correction_metrics = self.correction.to_dict()
        return {
            "case_count": self.cases,
            "error_detection": {
                "micro": {"tp": tp, "fp": fp, "fn": fn, **precision_recall_f1(tp, fp, fn)},
                "macro_f1": macro_f1,
                "exact_rule_set_accuracy": safe_divide(self.exact_matches, self.cases),
                "per_rule": per_rule,
                "case_classification_confusion_matrix": {
                    "positive_class": "COMPLIANT",
                    "tp": self.compliance.tp,
                    "fp": self.compliance.fp,
                    "fn": self.compliance.fn,
                    "tn": self.compliance.tn,
                },
            },
            "rule_retrieval": {
                "predicted_issues_evaluated": self.retrieval_total,
                "correct": self.retrieval_correct,
                "accuracy": safe_divide(self.retrieval_correct, self.retrieval_total),
            },
            "explanation_grounding": {
                "predicted_issues_evaluated": self.grounding_total,
                "structurally_grounded": self.grounding_supported,
                "grounded_rate": safe_divide(self.grounding_supported, self.grounding_total),
                "unsupported_claim_count": self.unsupported_claims,
                "unsupported_claim_rate": safe_divide(self.unsupported_claims, self.grounding_total),
                "metric_scope": "Automated evidence-contract check; not human semantic adjudication.",
            },
            "correction": {
                "eligibility_confusion": correction_metrics,
                "approved_attempts": self.correction_attempts,
                "successful_corrections": self.correction_successes,
                "correction_success_rate": safe_divide(
                    self.correction_successes, self.correction_attempts
                ),
                "revalidation_pass_rate": safe_divide(
                    self.revalidation_passes, self.correction_attempts
                ),
                "original_integrity_rate": safe_divide(
                    self.original_integrity_passes, self.correction_attempts
                ),
            },
            "agent_reliability": {
                "cases": self.cases,
                "tool_selection_successes": self.tool_selection_successes,
                "tool_selection_success_rate": safe_divide(
                    self.tool_selection_successes, self.cases
                ),
                "tool_calls": self.tool_calls,
                "failed_tool_calls": self.failed_tool_calls,
                "invalid_tool_calls": self.invalid_tool_calls,
            },
            "error_breakdown": {
                "counts": dict(sorted(self.error_counts.items())),
                "records": self.errors,
            },
        }


class EvaluationRunner:
    """Evaluate without passing ground truth, metadata, or injections to the agent."""

    def __init__(
        self,
        data_root: Path,
        *,
        agent_factory: Callable[[], ComplianceAgent] = ComplianceAgent,
    ) -> None:
        self.data_root = Path(data_root)
        self.agent_factory = agent_factory

    def evaluate(self, splits: tuple[str, ...] = ALLOWED_PHASE_12_SPLITS) -> dict:
        if not splits or any(split not in ALLOWED_PHASE_12_SPLITS for split in splits):
            raise ValueError("Phase 12 permits Development and Validation only; Final Test is sealed.")
        if len(set(splits)) != len(splits):
            raise ValueError("Evaluation splits must be unique.")

        return self._evaluate_authorized(splits, phase=12, final_test_accessed=False)

    def _evaluate_authorized(
        self,
        splits: tuple[str, ...],
        *,
        phase: int,
        final_test_accessed: bool,
    ) -> dict:
        """Internal scorer; callers must enforce the applicable split authorization."""

        accumulators = {split: _Accumulator() for split in splits}
        aggregate = _Accumulator()
        with TemporaryDirectory(prefix="zatca-evaluation-") as temp_dir:
            correction_root = Path(temp_dir)
            for split in splits:
                manifest = json.loads(
                    (self.data_root / "synthetic" / "v1" / "manifests" / f"{split}.json").read_text(
                        encoding="utf-8"
                    )
                )
                agent = self.agent_factory()
                analyses = []
                for case in manifest["cases"]:
                    invoice_path = self.data_root / case["invoice_file"]
                    if _sha256(invoice_path) != case["sha256"]:
                        raise ValueError(f"Invoice hash mismatch before inference: {case['case_id']}")
                    # The inference boundary intentionally contains only these two values.
                    analysis = agent.analyze(invoice_path, validation_date=EVALUATION_DATE)
                    analyses.append((case, invoice_path, analysis))

                # Ground truth is loaded only after inference has completed for the entire split.
                labels = _load_jsonl(self.data_root / "ground_truth" / "v1" / f"{split}.jsonl")
                if set(labels) != {case["case_id"] for case in manifest["cases"]}:
                    raise ValueError(f"Manifest and ground truth are misaligned for {split}.")
                for case, invoice_path, analysis in analyses:
                    expected = labels[case["case_id"]]
                    targets = [(split, accumulators[split])]
                    if len(splits) > 1:
                        targets.append(("aggregate", aggregate))
                    for scope, accumulator in targets:
                        self._score_case(
                            accumulator,
                            scope,
                            agent,
                            split,
                            case,
                            invoice_path,
                            analysis,
                            expected,
                            correction_root,
                        )

        split_results = {split: item.finalize() for split, item in accumulators.items()}
        aggregate_result = (
            next(iter(split_results.values())) if len(split_results) == 1 else aggregate.finalize()
        )
        result = {
            "evaluation_schema_version": "1.0.0",
            "phase": phase,
            "evaluation_date": EVALUATION_DATE.isoformat(),
            "allowed_splits": list(splits),
            "evaluated_splits": list(splits),
            "final_test_accessed": final_test_accessed,
            "agent_input_contract": ["invoice_path", "validation_date"],
            "ground_truth_loaded_after_split_inference": True,
            "llm_provider": None,
            "split_results": split_results,
            "aggregate": aggregate_result,
            "limitations": [
                "Development and Validation are engineering evaluation sets, not the final unseen test.",
                "Grounding is checked against a strict evidence contract, not by human semantic review.",
                "No live LLM provider is used; LLM-specific hallucination behavior is not measured here.",
                "Metrics cover only the eight selected rules and the frozen invoice profile.",
            ],
        }
        return result

    def _score_case(
        self,
        accumulator: _Accumulator,
        scope: str,
        agent: ComplianceAgent,
        split: str,
        case: dict,
        invoice_path: Path,
        analysis,
        expected: dict,
        correction_root: Path,
    ) -> None:
        accumulator.cases += 1
        case_id = case["case_id"]
        expected_rules = set(expected["expected_rule_ids"])
        predicted_rules = {
            check.rule_id for check in analysis.checks if check.status is CheckStatus.FAIL
        }
        if expected_rules == predicted_rules:
            accumulator.exact_matches += 1
        else:
            accumulator.error(
                "DETECTION_MISMATCH",
                split,
                case_id,
                {
                    "false_positive_rule_ids": sorted(predicted_rules - expected_rules),
                    "false_negative_rule_ids": sorted(expected_rules - predicted_rules),
                },
            )
        for rule_id in RULE_IDS:
            accumulator.rules[rule_id].update(rule_id in expected_rules, rule_id in predicted_rules)
        accumulator.compliance.update(
            bool(expected["expected_selected_checks_pass"]), analysis.selected_checks_pass
        )

        issues = {issue.rule_id: issue for issue in analysis.issues}
        for rule_id in predicted_rules:
            accumulator.retrieval_total += 1
            issue = issues.get(rule_id)
            retrieval_ok = bool(
                issue
                and issue.rule_id == rule_id
                and issue.evidence_status == "VERIFIED"
                and issue.sources
            )
            if retrieval_ok:
                accumulator.retrieval_correct += 1
            else:
                accumulator.error("RULE_RETRIEVAL_FAILURE", split, case_id, {"rule_id": rule_id})

            accumulator.grounding_total += 1
            expected_response = agent.retriever.retrieve_rule(rule_id)
            evidence = expected_response.hits[0].evidence if expected_response.hits else None
            expected_sources = (
                tuple((source.title, source.section, source.pages, source.url) for source in evidence.sources)
                if evidence
                else ()
            )
            actual_sources = (
                tuple((source.title, source.section, source.pages, source.url) for source in issue.sources)
                if issue
                else ()
            )
            combined_text = f"{issue.issue} {issue.why_flagged}".lower() if issue else ""
            banned = any(claim in combined_text for claim in BANNED_CLAIMS)
            grounding_ok = bool(
                issue
                and evidence
                and issue.applicable_requirement == evidence.meaning
                and issue.official_identifiers == evidence.official_identifiers
                and actual_sources == expected_sources
                and all(_is_official_zatca_url(source.url) for source in issue.sources)
                and not banned
            )
            if grounding_ok:
                accumulator.grounding_supported += 1
            else:
                accumulator.unsupported_claims += 1
                accumulator.error("GROUNDING_CONTRACT_FAILURE", split, case_id, {"rule_id": rule_id})

        failed_order = [check.rule_id for check in analysis.checks if check.status is CheckStatus.FAIL]
        expected_tools = ["validate_invoice"]
        if failed_order:
            expected_tools.extend("retrieve_zatca_rule" for _ in failed_order)
            expected_tools.extend(("explain_issues", "propose_safe_correction"))
        actual_tools = [event.tool_name for event in analysis.tool_trace]
        retrieved_order = [
            event.input_summary.get("rule_id")
            for event in analysis.tool_trace
            if event.tool_name == "retrieve_zatca_rule"
        ]
        tool_ok = (
            actual_tools == expected_tools
            and retrieved_order == failed_order
            and all(event.status is ToolCallStatus.SUCCESS for event in analysis.tool_trace)
        )
        if tool_ok:
            accumulator.tool_selection_successes += 1
        else:
            accumulator.error(
                "TOOL_SELECTION_FAILURE",
                split,
                case_id,
                {"expected_tools": expected_tools, "actual_tools": actual_tools},
            )
        accumulator.tool_calls += len(analysis.tool_trace)
        accumulator.failed_tool_calls += sum(
            event.status is ToolCallStatus.FAILED for event in analysis.tool_trace
        )
        accumulator.invalid_tool_calls += sum(
            event.error_type == "UnknownToolError" for event in analysis.tool_trace
        )

        expected_safe = bool(expected["safe_auto_correction"])
        observed_safe = bool(analysis.correction_proposal and analysis.correction_proposal.eligible)
        accumulator.correction.update(expected_safe, observed_safe)
        if expected_safe != observed_safe:
            accumulator.error(
                "CORRECTION_ELIGIBILITY_MISMATCH",
                split,
                case_id,
                {"expected_eligible": expected_safe, "predicted_eligible": observed_safe},
            )
        if observed_safe:
            accumulator.correction_attempts += 1
            before_hash = _sha256(invoice_path)
            output_path = correction_root / scope / f"{case_id}.corrected.xml"
            workflow = agent.correct_and_revalidate(
                invoice_path,
                validation_date=EVALUATION_DATE,
                approved=True,
                output_path=output_path,
            )
            success = bool(
                workflow.status is CorrectionWorkflowStatus.APPLIED_AND_REVALIDATED
                and workflow.comparison
                and workflow.comparison.after_selected_checks_pass
                and not workflow.comparison.remaining_rule_ids
                and not workflow.comparison.introduced_rule_ids
            )
            if success:
                accumulator.correction_successes += 1
                accumulator.revalidation_passes += 1
            else:
                accumulator.error("CORRECTION_FAILURE", split, case_id, {})
            if workflow.original_preserved and _sha256(invoice_path) == before_hash:
                accumulator.original_integrity_passes += 1
            else:
                accumulator.error("ORIGINAL_INTEGRITY_FAILURE", split, case_id, {})


def render_markdown(result: dict) -> str:
    aggregate = result["aggregate"]
    detection = aggregate["error_detection"]
    correction = aggregate["correction"]
    reliability = aggregate["agent_reliability"]
    lines = [
        f"# Phase {result['phase']} Evaluation Results",
        "",
        f"Evaluated splits: {', '.join(result['evaluated_splits'])}. Final Test accessed: **No**.",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Cases | {aggregate['case_count']} |",
        f"| Detection precision | {detection['micro']['precision']:.4f} |",
        f"| Detection recall | {detection['micro']['recall']:.4f} |",
        f"| Detection F1 | {detection['micro']['f1']:.4f} |",
        f"| Exact rule-set accuracy | {detection['exact_rule_set_accuracy']:.4f} |",
        f"| Rule retrieval accuracy | {aggregate['rule_retrieval']['accuracy']:.4f} |",
        f"| Explanation grounded rate | {aggregate['explanation_grounding']['grounded_rate']:.4f} |",
        f"| Correction eligibility F1 | {correction['eligibility_confusion']['f1']:.4f} |",
        f"| Correction success rate | {correction['correction_success_rate']:.4f} |",
        f"| Re-validation pass rate | {correction['revalidation_pass_rate']:.4f} |",
        f"| Tool-selection success rate | {reliability['tool_selection_success_rate']:.4f} |",
        f"| Invalid tool calls | {reliability['invalid_tool_calls']} |",
        f"| Unsupported claim rate | {aggregate['explanation_grounding']['unsupported_claim_rate']:.4f} |",
        "",
        "## Per-rule detection",
        "",
        "| Rule | TP | FP | FN | TN | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rule_id, metric in detection["per_rule"].items():
        lines.append(
            f"| {rule_id} | {metric['tp']} | {metric['fp']} | {metric['fn']} | {metric['tn']} | "
            f"{metric['precision']:.4f} | {metric['recall']:.4f} | {metric['f1']:.4f} |"
        )
    matrix = detection["case_classification_confusion_matrix"]
    lines.extend(
        [
            "",
            "## Case classification confusion matrix",
            "",
            "Positive class: `COMPLIANT`.",
            "",
            "| Actual / Predicted | COMPLIANT | NON_COMPLIANT |",
            "| --- | ---: | ---: |",
            f"| COMPLIANT | {matrix['tp']} | {matrix['fn']} |",
            f"| NON_COMPLIANT | {matrix['fp']} | {matrix['tn']} |",
            "",
            "## Error breakdown",
            "",
        ]
    )
    if aggregate["error_breakdown"]["counts"]:
        for category, count in aggregate["error_breakdown"]["counts"].items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("No errors were observed on the evaluated Development and Validation cases.")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            (
                "This is the frozen final unseen evaluation. No post-test tuning is permitted. "
                if result["phase"] == 13
                else "These are engineering results on Development and Validation, not the final unseen result. "
            )
            + "The grounding metric verifies exact evidence contracts and official source linkage; it is not a substitute for human semantic review. "
            + "No live LLM was evaluated in this run.",
            "",
            "Passing means: **Passed the selected checks implemented in this proof of concept.**",
            "",
        ]
    )
    return "\n".join(lines)


def write_results(result: dict, output_dir: Path, *, stem: str | None = None) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if stem is None:
        stem = "phase_12_development_validation" if result["phase"] == 12 else f"phase_{result['phase']}_results"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    return json_path, markdown_path


__all__ = ["ALLOWED_PHASE_12_SPLITS", "EVALUATION_DATE", "EvaluationRunner", "render_markdown", "write_results"]

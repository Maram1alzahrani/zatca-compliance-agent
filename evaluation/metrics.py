from __future__ import annotations

from dataclasses import dataclass


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


@dataclass(slots=True)
class BinaryCounter:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def update(self, expected: bool, predicted: bool) -> None:
        if expected and predicted:
            self.tp += 1
        elif not expected and predicted:
            self.fp += 1
        elif expected and not predicted:
            self.fn += 1
        else:
            self.tn += 1

    def to_dict(self) -> dict[str, int | float]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "support_positive": self.tp + self.fn,
            "support_negative": self.tn + self.fp,
            **precision_recall_f1(self.tp, self.fp, self.fn),
        }

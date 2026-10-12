"""Evaluate policy.decide() against a JSON file of labeled scenarios.

Each scenario is a Message (event + trust) plus an `expected_action` field, optionally with
`blast_radius` (default 1):

    [{"event": {...}, "trust": {...}, "expected_action": "ESCALATE"}, ...]

Usage:
    uv run python eval/run_eval.py eval/scenarios.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Scripts run with their own directory on sys.path, not the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from policy import decide  # noqa: E402
from schemas import Action, Message  # noqa: E402


def load_scenarios(path: Path) -> list[tuple[Message, Action, int]]:
    raw = json.loads(path.read_text())
    scenarios: list[tuple[Message, Action, int]] = []
    for i, item in enumerate(raw):
        try:
            expected = Action(item["expected_action"])
            blast_radius = int(item.get("blast_radius", 1))
            message = Message.model_validate({k: item[k] for k in ("event", "trust")})
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"{path}: scenario {i} is invalid: {exc!r}") from exc
        scenarios.append((message, expected, blast_radius))
    return scenarios


def evaluate(scenarios: list[tuple[Message, Action, int]]) -> list[tuple[Action, Action]]:
    """Return (expected, predicted) pairs."""
    return [
        (expected, decide(message, blast_radius=blast_radius).chosen_action)
        for message, expected, blast_radius in scenarios
    ]


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "  n/a"


def report(results: list[tuple[Action, Action]]) -> None:
    total = len(results)
    correct = sum(1 for expected, predicted in results if expected is predicted)
    print(f"Scenarios: {total}")
    print(f"Overall accuracy: {correct}/{total} = {_fmt(_ratio(correct, total))}\n")

    expected_counts = Counter(e for e, _ in results)
    predicted_counts = Counter(p for _, p in results)
    true_positives = Counter(e for e, p in results if e is p)

    print(f"{'action':<20} {'precision':>9} {'recall':>7} {'support':>8} {'predicted':>10}")
    for action in Action:
        tp = true_positives[action]
        precision = _ratio(tp, predicted_counts[action])
        recall = _ratio(tp, expected_counts[action])
        print(
            f"{action.value:<20} {_fmt(precision):>9} {_fmt(recall):>7} "
            f"{expected_counts[action]:>8} {predicted_counts[action]:>10}"
        )

    mistakes = Counter((e, p) for e, p in results if e is not p)
    if mistakes:
        print("\nMost common misclassifications (expected -> predicted):")
        for (expected, predicted), count in mistakes.most_common(5):
            print(f"  {expected.value} -> {predicted.value}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the decision policy on scenarios.")
    parser.add_argument("scenarios", type=Path, help="JSON file of labeled scenarios")
    args = parser.parse_args()

    report(evaluate(load_scenarios(args.scenarios)))


if __name__ == "__main__":
    main()

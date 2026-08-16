"""Reproducible evaluation for the heuristic AI-video detector.

The manifest must be JSON Lines with one independently labeled item per line:

{"path": "videos/example.mp4", "label": "ai", "source": "Dataset name",
 "notes": "Why this label is trusted"}

Labels must be ``ai`` or ``authentic``. Paths are resolved relative to the
manifest file. This script reports measurements; it never invents labels.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from detect_ai_video import analyze_video_characteristics


VALID_LABELS = {"ai", "authentic"}


def _metric(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def run_benchmark(manifest_path: str) -> dict[str, Any]:
    """Run the detector against every labeled item in a JSONL manifest."""
    manifest_path = os.path.abspath(manifest_path)
    root = os.path.dirname(manifest_path)
    items: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    with open(manifest_path, "r", encoding="utf-8") as manifest:
        for line_number, raw_line in enumerate(manifest, start=1):
            if not raw_line.strip():
                continue
            item = json.loads(raw_line)
            label = str(item.get("label", "")).strip().lower()
            relative_path = str(item.get("path", "")).strip()
            if label not in VALID_LABELS or not relative_path:
                skipped.append({
                    "line": str(line_number),
                    "reason": "path and label (ai/authentic) are required",
                })
                continue

            video_path = relative_path
            if not os.path.isabs(video_path):
                video_path = os.path.join(root, video_path)
            if not os.path.isfile(video_path):
                skipped.append({
                    "line": str(line_number),
                    "reason": f"file not found: {relative_path}",
                })
                continue

            result = analyze_video_characteristics(video_path)
            items.append({
                "path": relative_path,
                "source": item.get("source", "unspecified"),
                "notes": item.get("notes", ""),
                "expected": label,
                "predicted": "ai" if result["is_ai_generated"] else "authentic",
                "correct": (result["is_ai_generated"] == (label == "ai")),
                "score": result["ai_score"],
                "confidence": result["confidence"],
                "factors": result["detection_factors"],
            })

    tp = sum(i["expected"] == "ai" and i["predicted"] == "ai" for i in items)
    tn = sum(i["expected"] == "authentic" and i["predicted"] == "authentic" for i in items)
    fp = sum(i["expected"] == "authentic" and i["predicted"] == "ai" for i in items)
    fn = sum(i["expected"] == "ai" and i["predicted"] == "authentic" for i in items)
    ai_count = tp + fn
    authentic_count = tn + fp

    precision = _metric(tp, tp + fp)
    recall = _metric(tp, ai_count)
    specificity = _metric(tn, authentic_count)
    f1 = (
        round(2 * precision * recall / (precision + recall), 4)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    balanced_accuracy = (
        round((recall + specificity) / 2, 4)
        if recall is not None and specificity is not None
        else None
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": os.path.basename(manifest_path),
        "sample_count": len(items),
        "class_counts": {"ai": ai_count, "authentic": authentic_count},
        "metrics": {
            "accuracy": _metric(tp + tn, len(items)),
            "precision": precision,
            "recall_sensitivity": recall,
            "specificity": specificity,
            "f1": f1,
            "balanced_accuracy": balanced_accuracy,
        },
        "confusion_matrix": {
            "true_positive_ai": tp,
            "true_negative_authentic": tn,
            "false_positive_authentic_called_ai": fp,
            "false_negative_ai_called_authentic": fn,
        },
        "items": items,
        "skipped": skipped,
        "warning": (
            "Metrics are only as trustworthy as the independent labels and dataset coverage. "
            "This is not a universal accuracy guarantee."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="Path to a labeled JSONL manifest")
    parser.add_argument("--output", help="Optional JSON report output path")
    args = parser.parse_args()
    report = run_benchmark(args.manifest)
    rendered = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            output.write(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
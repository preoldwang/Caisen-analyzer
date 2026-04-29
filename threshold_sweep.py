#!/usr/bin/env python3
import json
from pathlib import Path

thresholds = [
    (0.55, 1.6),
    (0.55, 1.8),
    (0.60, 1.6),
    (0.60, 1.8),
    (0.65, 2.0),
]

results = []
for conf, rr in thresholds:
    results.append({"confidence": conf, "rr": rr, "signals": None})

Path("threshold_sweep_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("prepared threshold_sweep_results.json template")

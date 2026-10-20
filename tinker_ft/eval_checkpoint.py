"""Score a saved Tinker checkpoint (and the rules baseline) on any labelled .jsonl file, without retraining.
Usage:  python -m tinker_ft.eval_checkpoint data/firststep_unseen.jsonl
Needs TINKER_API_KEY and TINKER_SAMPLER_PATH (the tinker://... path) in the environment."""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.firststep import CATEGORIES, VIABLE, classify_rules
from app.llm import TinkerClient


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def main(path: str) -> None:
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    client = TinkerClient(os.environ["TINKER_API_KEY"], os.environ["TINKER_SAMPLER_PATH"], timeout=60)

    def ask(r: dict) -> str:
        try:
            out = client.judge_first_step(r["statement"], r["text"])
        except Exception as e:  # count failures as wrong, do not hide them
            print("call failed:", e)
            out = None
        return out if out in CATEGORIES else "INVALID"

    with ThreadPoolExecutor(max_workers=4) as ex:
        model = list(ex.map(ask, rows))
    rules = [classify_rules(r["statement"], r["text"]) for r in rows]

    for name, preds in (("Fine-tuned model", model), ("Rules baseline", rules)):
        ok = sum(p == r["label"] for p, r in zip(preds, rows))
        viable = sum((p in VIABLE) == (r["label"] in VIABLE) for p, r in zip(preds, rows))
        lo, hi = wilson(ok, len(rows))
        print(f"\n{name}: exact {ok}/{len(rows)} = {ok/len(rows):.0%} (95% CI {lo:.0%}-{hi:.0%}); "
              f"viable-vs-not {viable/len(rows):.0%}")
        by = defaultdict(lambda: [0, 0])
        for p, r in zip(preds, rows):
            by[r["problem_id"]][1] += 1
            by[r["problem_id"]][0] += p == r["label"]
        for pid, (k, n) in by.items():
            print(f"  {pid}: {k}/{n}")
    print("\nModel mistakes (true -> predicted):")
    for p, r in zip(model, rows):
        if p != r["label"]:
            print(f"  {r['label']} -> {p}: {r['text']}")
    print("\nModel confusion:", dict(Counter((r["label"], p) for p, r in zip(model, rows) if p != r["label"])))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/firststep_unseen.jsonl")
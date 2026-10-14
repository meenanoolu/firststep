"""SYNTHETIC labelled first-step sentences for the Tinker experiment (written by the project author, not real learners).

Held out two ways: test uses different PROBLEMS and different TEMPLATES than train, so a model cannot just memorise
phrasings. Real learner sentences (your brother's sessions) should replace/extend the test set before any claim.
Templates 0-2 per label go to train, 3-4 to test. 'Hard' templates avoid the keywords the rule baseline looks for.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.problems import PROBLEMS  # noqa: E402

SLOTS = {  # obj, tiny example, thing to track, thing to try all of
    "max-subarray": ("the numbers", "a list with one negative number", "the best sum ending at each position", "block"),
    "count-pairs-sum": ("the list", "the list 2 2 with target 4", "which earlier values complete the target", "pair"),
    "longest-equal-run": ("the list", "a list of three equal numbers", "the length of the current streak", "start position"),
    "balanced-brackets": ("the string", "the string )(", "the brackets that are still open", "way to cancel neighbours"),
    "range-sum-queries": ("the array", "a query that starts at position 1", "the total of everything before each position", "query"),
    "second-largest-distinct": ("the numbers", "the list 3 3 1", "the biggest value and the best one below it", "value"),
}
T = {
 "too_vague": ["I would think about {o} and write the code once I get it", "Probably some loop over {o} and a condition somewhere, then print",
               "I will try to figure out the correct approach for {o} step by step", "Use the usual algorithm for this kind of task",
               "Not sure yet, I will see what comes out when I start typing code for {o}"],
 "restate": ["So we are given {o} and we must print the required value from it", "The task is to read {o} and output the answer the statement asks for",
             "We need to process {o} and produce the result described in the problem", "Basically read the input and print what they want about {o}",
             "The problem wants us to look at {o} and compute the final value"],
 "small_example": ["Let me take {t} and work out the answer by hand", "First a small example: {t}, and see what should be printed",
                   "I would write down {t} and solve it on paper", "Take {t}; what the right output is there tells me what to handle",
                   "Start from {t} and trace through what a program must do"],
 "brute_force": ["I would check every {b} and keep the best one", "Brute force: try all {b}s with nested loops and compare",
                 "Try every possible {b} one after another and take the max or count", "Loop over each {b} in turn, test it, and remember the result",
                 "For each {b}, compute the value directly and compare with the best so far"],
 "observation": ["I would keep track of {k} while going through {o}", "I notice the answer depends on {k}, so I only need to remember that",
                 "The key thing to remember as I scan is {k}", "As I go along I only need {k}, nothing else",
                 "What matters at each step is {k}, so I would store it"],
}
TEST_PROBLEMS = {"balanced-brackets", "range-sum-queries"}


def build(seed: int = 1):
    rng = random.Random(seed)
    train, test = [], []
    for pid, p in PROBLEMS.items():
        o, t, k, b = SLOTS[pid]
        for label, tpls in T.items():
            for i, tpl in enumerate(tpls):
                text = tpl.format(o=o, t=t, k=k, b=b)
                row = {"problem_id": pid, "statement": p.statement, "text": text, "label": label}
                (test if (pid in TEST_PROBLEMS and i >= 3) else train if (pid not in TEST_PROBLEMS and i < 3) else []).append(row)
    rng.shuffle(train)
    return train, test


if __name__ == "__main__":
    from app.firststep import classify_rules, VIABLE
    tr, te = build()
    out = Path(__file__).resolve().parent.parent / "data"
    out.mkdir(exist_ok=True)
    for name, rows in (("firststep_train.jsonl", tr), ("firststep_test.jsonl", te)):
        (out / name).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    pred = [classify_rules(r["statement"], r["text"]) for r in te]
    acc = sum(p == r["label"] for p, r in zip(pred, te)) / len(te)
    via = sum((p in VIABLE) == (r["label"] in VIABLE) for p, r in zip(pred, te)) / len(te)
    print(f"train={len(tr)} test={len(te)}  rules baseline: 5-way accuracy={acc:.2f}  viable-vs-not accuracy={via:.2f}")
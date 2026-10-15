"""Find and minimise a failing input for a learner's program.

The oracle is the problem's trusted `solve`. Order: samples -> hand-written edge cases -> seeded random
cases (small first). The first failure is shrunk greedily (delta-debugging style) within a budget.
"""
from __future__ import annotations

import random
import time

from .problems.base import Problem
from .runner import OK, Program, same_output


def _measure(p: Problem, case) -> tuple[int, int]:
    return (p.size(case), len(p.fmt(case)))


def _check(p: Problem, prog: Program, case) -> tuple[bool, str, str, str]:
    """-> (failed, expected, got, verdict)"""
    exp = p.solve(case)
    r = prog.run(p.fmt(case))
    if r.verdict != OK:
        return True, exp, r.detail or r.verdict, r.verdict
    return (not same_output(exp, r.stdout)), exp, r.stdout.strip(), OK


def shrink(p: Problem, prog: Program, case, budget: int = 80, until: float | None = None):
    """Greedy shrink. Returns (smallest failing case, runs used)."""
    best, used, improved = case, 0, True
    while improved and used < budget:
        improved = False
        for cand in p.shrinks(best):
            if _measure(p, cand) >= _measure(p, best):
                continue
            if used >= budget or (until is not None and time.monotonic() > until):
                break
            used += 1
            failed = _check(p, prog, cand)[0]
            if failed:
                best, improved = cand, True
                break
    return best, used


def find_counterexample(p: Problem, language: str, code: str, *, budget: int = 150, shrink_budget: int = 80,
                        seed: int = 7, timeout: float = 2.0, program=None, deadline_s: float | None = None) -> dict:
    """`program` lets the evaluation inject a faster in-process executor with the same .run() interface."""
    prog = program or Program.prepare(language, code, timeout)
    until = None if deadline_s is None else time.monotonic() + deadline_s   # stops a slow program from hogging a worker
    try:
        if prog.verdict != OK:
            return {"status": "cannot_run", "verdict": prog.verdict, "detail": prog.detail, "tests_run": 0}
        tests = 0
        # 1. the public samples
        for sin, sout in p.samples:
            if until is not None and time.monotonic() > until:
                return {"status": "too_slow", "tests_run": tests}
            tests += 1
            r = prog.run(sin)
            if r.verdict != OK or not same_output(sout, r.stdout):
                return {"status": "fails_sample", "tests_run": tests, "input": sin, "expected": sout.strip(),
                        "got": (r.detail or r.stdout).strip(), "verdict": r.verdict, "features": [],
                        "size_before": None, "size_after": None}
        # 2. edge cases, then 3. random
        rng = random.Random(seed)
        pool = list(p.edge_cases()) + [p.gen(rng, i) for i in range(budget)]
        for case in pool:
            if until is not None and time.monotonic() > until:
                return {"status": "too_slow", "tests_run": tests}
            tests += 1
            failed, exp, got, verdict = _check(p, prog, case)
            if failed:
                before = p.size(case)
                small, used = shrink(p, prog, case, shrink_budget, until)
                _, exp2, got2, verdict2 = _check(p, prog, small)
                return {"status": "found", "tests_run": tests + used, "input": p.fmt(small), "expected": exp2,
                        "got": got2, "verdict": verdict2, "features": p.features(small),
                        "size_before": before, "size_after": p.size(small)}
        return {"status": "none_found", "tests_run": tests}
    finally:
        if program is None:
            prog.close()
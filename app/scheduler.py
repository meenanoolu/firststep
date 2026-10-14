"""Closed-book re-solve schedule. Pure functions so they are trivial to test.

The intervals (1,3,7,21 days by default) are a configurable heuristic, NOT a proven optimum:
the retrieval-practice literature supports spaced, closed-book retrieval but does not show one
best schedule, and most of it is from text recall rather than coding."""
from __future__ import annotations

DAY = 86400.0
INDEPENDENT, HINTED, NOT_SOLVED = "independent", "hinted", "not_solved"


def first_due(now: float, intervals: tuple[int, ...]) -> float:
    return now + intervals[0] * DAY


def after_review(stage: int, outcome: str, now: float, intervals: tuple[int, ...]):
    """-> (new_stage, due_ts or None). stage = index of the interval that was just used."""
    if outcome == INDEPENDENT:
        nxt = stage + 1
        if nxt >= len(intervals):
            return nxt, None  # finished the ladder
        return nxt, now + intervals[nxt] * DAY
    if outcome == HINTED:
        return stage, now + intervals[stage] * DAY
    if outcome == NOT_SOLVED:
        return 0, now + intervals[0] * DAY
    raise ValueError(f"unknown outcome {outcome!r}")
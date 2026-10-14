"""Graded hints. Static, human-written hints are always the fallback; a model may only REPHRASE one,
and the rephrase must pass the same leak check or it is discarded."""
from __future__ import annotations

from . import leakcheck
from .problems.base import Problem


def get_hint(p: Problem, level: int, llm=None) -> dict:
    level = max(1, min(4, level))
    base = p.hints[level - 1]
    if llm is not None:
        try:
            cand = llm.rephrase_hint(p.statement, base, level)
        except Exception:
            cand = None
        if cand:
            ok, reasons = leakcheck.check(cand, p, level)
            if ok:
                return {"level": level, "text": cand, "source": "model", "rejected": None}
            return {"level": level, "text": base, "source": "static", "rejected": reasons}
    return {"level": level, "text": base, "source": "static", "rejected": None}
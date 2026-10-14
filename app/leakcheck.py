"""Leak checker: every hint, human-written or model-written, must pass before a learner sees it.
Rules are plain code so they are testable and the model cannot talk its way past them."""
from __future__ import annotations

import re

from .problems.base import Problem

_ANSWER_PHRASES = ("the solution is", "here is the solution", "here's the solution",
                   "here is the code", "here's the code", "copy this", "just use this", "full solution")
_CODE_LINE = re.compile(r"^\s*(def |class |for .+ in .+:|while .+:|if .+:|return\b|print\(|#include|int main|"
                        r"using namespace|import )", re.M)
_TOKEN = re.compile(r"\w+|[^\w\s]")


def _tokens(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s)]


def ngram_overlap(text: str, ref: str, n: int = 5) -> bool:
    t, r = _tokens(text), _tokens(ref)
    def words(g):  # grams that are mostly punctuation ("[ l - 1 ]") are not a meaningful copy
        return sum(x[0].isalnum() or x[0] == "_" for x in g) >= 3
    ref_grams = {tuple(r[i:i + n]) for i in range(len(r) - n + 1) if words(r[i:i + n])}
    return any(tuple(t[i:i + n]) in ref_grams for i in range(len(t) - n + 1))


def check(text: str, problem: Problem, level: int) -> tuple[bool, list[str]]:
    """Return (ok, reasons). `level` is the hint level (1..4) the text is meant to be shown at."""
    reasons: list[str] = []
    low = text.lower()
    if "```" in text or _CODE_LINE.search(text):
        reasons.append("contains code")
    if any(p in low for p in _ANSWER_PHRASES) or re.search(r"(?<!what )(?<!what's )the answer is\b(?! (when|if))", low):
        reasons.append("states the answer")
    if ngram_overlap(text, problem.reference_src):
        reasons.append("copies the reference solution")
    for term, min_level in problem.spoilers.items():
        if term.lower() in low and level < min_level:
            reasons.append(f"uses '{term}' too early")
    if len(text) > 900:
        reasons.append("too long")
    return (not reasons), reasons
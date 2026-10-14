"""First-step check: before any coding, the learner writes ONE sentence about how they would start.
Categories (restate / small_example / brute_force / observation / too_vague). Viable = the last three.
A model may classify, but only into these labels; anything else falls back to the rules below."""
from __future__ import annotations

import re

CATEGORIES = ("restate", "small_example", "brute_force", "observation", "too_vague")
VIABLE = {"brute_force", "small_example", "observation"}

_W = re.compile(r"[a-z0-9]+")
_BRUTE = ("try all", "every pair", "all pairs", "all subarrays", "every subarray", "brute", "nested loop",
          "check every", "check all", "every possible", "each pair", "all possible", "two loops",
          "one by one", "go through", "iterate", "walk through", "add each", "add all")
_EXAMPLE = ("example", "for instance", "e.g", "small case", "tiny case", "by hand", "let's say", "suppose")
_OBS = ("notice", "observe", "keep track", "track", "running", "remember", "store", "because", "depends on",
        "only need", "so that")

FEEDBACK = {
    "restate": "That repeats the statement. Say what YOU would do first, e.g. work a tiny example by hand.",
    "too_vague": "Too vague to act on. Name a concrete first move: a tiny example, a try-everything loop, "
                 "or one thing you would keep track of.",
    "small_example": "Good start: working a small example by hand is a real first step.",
    "brute_force": "Good start: a try-everything version is a valid first step, even if it is slow.",
    "observation": "Good start: you named something to keep track of.",
}


def classify_rules(statement: str, text: str) -> str:
    low = text.lower()
    words = _W.findall(low)
    if len(words) < 6:
        return "too_vague"
    st = set(_W.findall(statement.lower()))
    if words and sum(w in st for w in words) / len(words) >= 0.8:
        return "restate"
    if any(k in low for k in _BRUTE):
        return "brute_force"
    if any(k in low for k in _EXAMPLE) or len(re.findall(r"\d+", low)) >= 2:
        return "small_example"
    if any(k in low for k in _OBS):
        return "observation"
    return "too_vague"


def judge(statement: str, text: str, llm=None) -> dict:
    source, cat = "rules", None
    if llm is not None:
        try:
            cand = llm.judge_first_step(statement, text)
        except Exception:
            cand = None
        if cand in CATEGORIES:
            cat, source = cand, "model"
    if cat is None:
        cat = classify_rules(statement, text)
    return {"category": cat, "viable": cat in VIABLE, "feedback": FEEDBACK[cat], "source": source}
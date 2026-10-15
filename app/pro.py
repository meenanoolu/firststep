"""The paid 'full learning report': a weekly trend, your real first-step sentences, and a practice plan.
Everything here is plain code over the learner's own data. No model is involved, so it costs nothing to serve.
Unlock codes: PRO_CODES (hand-issued) and/or Gumroad license keys (one per sale, verified over HTTPS)."""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import json
import random

import httpx

from .config import Settings
from .problems import PROBLEMS
from .store import Store


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def code_is_valid(s: Settings, code: str, post=httpx.post) -> bool:
    code = code.strip()
    if len(code) < 8:
        return False
    if code in s.pro_codes:
        return True
    if s.gumroad_product_id:
        try:
            r = post("https://api.gumroad.com/v2/licenses/verify", timeout=10, data={
                "product_id": s.gumroad_product_id, "license_key": code, "increment_uses_count": "false"})
            j = r.json()
        except Exception:
            return False
        p = j.get("purchase") or {}
        return bool(j.get("success")) and not p.get("refunded") and not p.get("chargebacked")
    return False


@functools.lru_cache(maxsize=1)
def problem_features() -> dict[str, frozenset[str]]:
    """Which edge-features each problem can exercise, found by running its own case generators."""
    out = {}
    for pid, p in PROBLEMS.items():
        rng = random.Random(0)
        cases = list(p.edge_cases()) + [p.gen(rng, i) for i in range(60)]
        out[pid] = frozenset(f for c in cases for f in p.features(c))
    return out


def next_up(profile: dict[str, int], practised: dict[str, str], titles: dict[str, str], limit: int = 3) -> list[dict]:
    """Rank problems by how many of the learner's recurring mistakes they exercise. practised: pid -> status."""
    feats, plan = problem_features(), []
    for pid, fs in feats.items():
        hit = {f: n for f, n in profile.items() if f in fs}
        if not hit:
            continue
        status = practised.get(pid)
        if status == "mastered":
            continue
        plan.append({"problem_id": pid, "title": titles.get(pid, pid), "score": sum(hit.values()),
                     "because": sorted(hit, key=hit.get, reverse=True), "new": status is None})
    plan.sort(key=lambda x: (-x["score"], not x["new"], x["title"]))
    return plan[:limit]


def _week(day: int) -> int:
    return (day + 3) // 7  # weeks start on Monday (day 0 of the epoch was a Thursday)


def trend(st: Store, learner: str, tz_offset_min: int = 0) -> list[dict]:
    off = tz_offset_min * 60
    sess = [s for s in st.all("SELECT * FROM sessions WHERE learner=? AND finished IS NOT NULL ORDER BY id", (learner,))]
    found: dict[int, int] = {}
    for r in st.all("SELECT session_id FROM submissions WHERE learner=? AND status='found'", (learner,)):
        found[r["session_id"]] = found.get(r["session_id"], 0) + 1
    weeks: dict[int, list] = {}
    for s in sess:
        weeks.setdefault(_week(int((s["finished"] + off) // 86400)), []).append(s)
    out = []
    for w in sorted(weeks):
        ss = weeks[w]
        start = dt.date(1970, 1, 1) + dt.timedelta(days=w * 7 - 3)
        out.append({"week_of": start.isoformat(), "sessions": len(ss),
                    "avg_hints": round(sum(x["hints_used"] for x in ss) / len(ss), 2),
                    "failing_inputs_found": sum(found.get(x["id"], 0) for x in ss),
                    "solved": sum(x["outcome"] in ("independent", "hinted") for x in ss)})
    return out


def pro_report(st: Store, learner: str, base: dict, titles: dict[str, str], tz_offset_min: int = 0) -> dict:
    practised = {p["problem_id"]: p["status"] for p in base["problems"]}
    steps = st.all("SELECT problem_id, first_step_text, first_step_cat FROM sessions WHERE learner=? "
                   "AND first_step_text IS NOT NULL AND first_step_text != '' ORDER BY id DESC LIMIT 10", (learner,))
    return {"trend": trend(st, learner, tz_offset_min),
            "next_up": next_up(base["failure_profile"], practised, titles),
            "first_steps": [{"problem": titles.get(r["problem_id"], r["problem_id"]), "text": r["first_step_text"],
                             "category": r["first_step_cat"]} for r in steps]}

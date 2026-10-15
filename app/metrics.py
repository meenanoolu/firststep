"""Numbers the app can report about itself. No claim without one of these behind it."""
from __future__ import annotations

import json
import time
from collections import Counter

from .store import Store


def learner_stats(st: Store, learner: str) -> dict:
    sess = st.all("SELECT * FROM sessions WHERE learner=?", (learner,))
    done = [s for s in sess if s["finished"]]
    reviews = st.all("SELECT * FROM reviews WHERE learner=? AND done_ts IS NOT NULL", (learner,))
    ind = sum(r["outcome"] == "independent" for r in reviews)
    ttf = [s["first_step_ts"] - s["created"] for s in sess if s["first_step_ts"]]
    prof: Counter = Counter()
    for r in st.all("SELECT features FROM submissions WHERE learner=? AND status='found'", (learner,)):
        prof.update(json.loads(r["features"] or "[]"))
    return {
        "sessions": len(sess), "finished": len(done),
        "avg_hints": round(sum(s["hints_used"] for s in done) / len(done), 2) if done else None,
        "avg_seconds_to_first_step": round(sum(ttf) / len(ttf), 1) if ttf else None,
        "reviews_done": len(reviews),
        "unaided_restart_rate": round(ind / len(reviews), 2) if reviews else None,
        "failure_profile": dict(prof.most_common()),
        "first_step_viable_rate": _rate(sess),
    }


def _rate(sess):
    c = [s["first_step_cat"] for s in sess if s["first_step_cat"]]
    return round(sum(x in ("brute_force", "small_example", "observation") for x in c) / len(c), 2) if c else None


def model_stats(st: Store) -> dict:
    rows = st.all("SELECT job, accepted, COUNT(*) n FROM model_calls GROUP BY job, accepted")
    out: dict = {}
    for r in rows:
        out.setdefault(r["job"], {"accepted": 0, "rejected": 0})["accepted" if r["accepted"] else "rejected"] = r["n"]
    return out


def _streak(days: set[int], today: int) -> int:
    """Consecutive active days ending today (or yesterday, so a streak is not lost before you practise today)."""
    d = today if today in days else today - 1
    n = 0
    while d in days:
        n, d = n + 1, d - 1
    return n


def learner_report(st: Store, learner: str, titles: dict[str, str], intervals: tuple[int, ...],
                   tz_offset_min: int = 0, now: float | None = None) -> dict:
    """Everything the report page and the home dashboard show. Pure reads, no model involved."""
    now = now or time.time()
    off = tz_offset_min * 60
    day = lambda ts: int((ts + off) // 86400)
    sess = st.all("SELECT * FROM sessions WHERE learner=? ORDER BY id", (learner,))
    subs = st.all("SELECT session_id, status, features FROM submissions WHERE learner=? ORDER BY id", (learner,))
    open_rv = {r["problem_id"]: r for r in st.upcoming_reviews(learner)}
    by_sess: dict[int, list[str]] = {}
    for r in subs:
        if r["status"] == "found":
            by_sess.setdefault(r["session_id"], []).extend(json.loads(r["features"] or "[]"))
    problems = []
    for pid, title in titles.items():
        mine = [s for s in sess if s["problem_id"] == pid and s["finished"]]
        if not sess or not any(s["problem_id"] == pid for s in sess):
            continue
        rv = open_rv.get(pid)
        if rv:
            rung, status = rv["stage"], "due" if rv["due_ts"] <= now else "waiting"
            next_due_days = round((rv["due_ts"] - now) / 86400, 1)
        else:
            rung, status, next_due_days = (len(intervals), "mastered", None) if mine else (0, "in_progress", None)
        problems.append({"problem_id": pid, "title": title, "sessions": len(mine), "rungs_done": rung,
                         "ladder_len": len(intervals), "status": status, "next_due_days": next_due_days})
    history = [{"problem": titles.get(s["problem_id"], s["problem_id"]), "first_step": s["first_step_cat"],
                "hints": s["hints_used"], "outcome": s["outcome"], "review": bool(s["review_id"]),
                "broke_on": sorted(set(by_sess.get(s["id"], [])))} for s in sess[-15:] if s["finished"]][::-1]
    active = {day(s["finished"]) for s in sess if s["finished"]}
    base = learner_stats(st, learner)
    base.update({"problems": problems, "history": history, "streak_days": _streak(active, day(now)),
                 "mastered": sum(p["status"] == "mastered" for p in problems),
                 "due_now": sum(p["status"] == "due" for p in problems)})
    return base
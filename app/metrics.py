"""Numbers the app can report about itself. No claim without one of these behind it."""
from __future__ import annotations

import json
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
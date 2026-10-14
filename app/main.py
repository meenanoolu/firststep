"""FirstStep API. Run: uvicorn app.main:app"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import firststep, observability, leakcheck, metrics, scheduler
from .config import Settings, get_settings
from .counterexample import find_counterexample
from .hints import get_hint
from .llm import get_client
from .problems import PROBLEMS
from .store import Store

STATIC = Path(__file__).parent / "static"

EXPLAIN = {
    "all_negative": "Your program was run on numbers that are all below zero. Check what it does when no choice is positive.",
    "single_element": "The smallest possible input, one element, breaks your program. Trace it by hand.",
    "self_pair_trap": "An element that could pair with itself matters here. Check whether your code counts a position against itself.",
    "duplicates": "Repeated values matter in this input. Check how your code treats equal numbers at different positions.",
    "all_equal": "Every number is the same here. Check what your code assumes about differences.",
    "max_repeated": "The largest value appears more than once. Check what your code does the second time it sees it.",
    "has_zero": "A zero is involved. Check any place where you treat 'nothing' and 'zero' as the same.",
    "longest_run_at_end": "The best streak is the last one in the list. Check when your code compares the best.",
    "starts_with_closer": "The string starts with a closing bracket. Check what your code does when there is nothing open.",
    "closer_on_empty": "A closing bracket arrives when nothing is open. Check how your code handles that.",
    "wrong_type_closer": "A closing bracket arrives that does not match the latest opener. Check how you compare them.",
    "unclosed_opener": "Everything seems to match, but something is left open at the end. Check your final step.",
    "odd_length": "The string has odd length, so it cannot be balanced. Check your final answer.",
    "query_starts_at_1": "A query starts at position 1. Check the index you use for 'everything before'.",
    "single_element_query": "A query covers one position only. Trace it by hand.",
}


class NewSession(BaseModel):
    learner: str = Field(min_length=6, max_length=64)
    problem_id: str
    review_id: int | None = None


class Text(BaseModel):
    text: str = Field(min_length=1, max_length=600)


class Submit(BaseModel):
    language: str = "python"
    code: str = Field(min_length=1, max_length=20000)


class Finish(BaseModel):
    solved: bool


class Shift(BaseModel):
    learner: str
    days: int = 1


def create_app(settings: Settings | None = None, llm="auto") -> FastAPI:
    s = settings or get_settings()
    st = Store(s.db_path)
    observability.init()
    client = get_client(s) if llm == "auto" else llm
    sem = asyncio.Semaphore(max(1, s.max_concurrent_runs))
    app = FastAPI(title="FirstStep")

    def sess_or_404(sid: int) -> dict:
        row = st.session(sid)
        if not row:
            raise HTTPException(404, "no such session")
        return row

    @app.get("/api/health")
    def health():
        return {"ok": True, "model": client.name if client else "none", "dev_mode": s.dev_mode}

    @app.get("/api/config")
    def config():
        url = s.payment_url if s.payment_url.startswith("https://") else ""
        return {"payment_url": url, "payment_label": s.payment_label}

    @app.get("/api/problems")
    def problems():
        return [{k: v for k, v in p.public().items() if k in ("id", "title", "difficulty", "tags")}
                for p in PROBLEMS.values()]

    @app.get("/api/problems/{pid}")
    def problem(pid: str):
        if pid not in PROBLEMS:
            raise HTTPException(404, "no such problem")
        return PROBLEMS[pid].public()

    @app.post("/api/sessions")
    def new_session(b: NewSession):
        if b.problem_id not in PROBLEMS:
            raise HTTPException(404, "no such problem")
        if b.review_id is not None:
            rv = st.review(b.review_id)
            if not rv or rv["learner"] != b.learner or rv["done_ts"]:
                raise HTTPException(400, "bad review")
        return {"session_id": st.new_session(b.learner, b.problem_id, b.review_id)}

    @app.post("/api/sessions/{sid}/first-step")
    def first_step(sid: int, b: Text):
        row = sess_or_404(sid)
        p = PROBLEMS[row["problem_id"]]
        res = firststep.judge(p.statement, b.text, client)
        if client:
            st.log_model("judge_first_step", res["source"] == "model", "" if res["source"] == "model" else "invalid label")
        st.set_first_step(sid, res["category"])
        return res

    @app.post("/api/sessions/{sid}/hint")
    def hint(sid: int):
        row = sess_or_404(sid)
        if row["finished"]:
            raise HTTPException(400, "session finished")
        used = row["hints_used"]
        if used >= 4:
            raise HTTPException(400, "no more hints")
        if used >= 1 and st.submissions_in_session(sid) <= used:
            raise HTTPException(429, "Run your code again before asking for the next hint.")
        res = get_hint(PROBLEMS[row["problem_id"]], used + 1, client)
        if client:
            st.log_model("rephrase_hint", res["source"] == "model", ",".join(res["rejected"] or []))
        st.bump_hint(sid)
        return {"level": res["level"], "text": res["text"], "source": res["source"]}

    @app.post("/api/sessions/{sid}/submit")
    async def submit(sid: int, b: Submit):
        row = sess_or_404(sid)
        if row["finished"]:
            raise HTTPException(400, "session finished")
        if st.submissions_last_day(row["learner"]) >= s.max_submits_per_day:
            raise HTTPException(429, "Daily run limit reached. Come back tomorrow.")
        p = PROBLEMS[row["problem_id"]]
        async with sem:
            with observability.work_span("find_counterexample", problem=p.id, language=b.language):
                res = await asyncio.to_thread(find_counterexample, p, b.language, b.code, budget=s.finder_budget,
                                              shrink_budget=s.shrink_budget, timeout=s.run_timeout_s)
        st.add_submission(sid, row["learner"], b.language, b.code if s.store_code else "", res["status"],
                          res.get("features", []), res.get("tests_run", 0), res.get("size_before"), res.get("size_after"))
        if res["status"] == "found":
            expl = None
            if client:
                try:
                    cand = client.explain_counterexample(p.statement, res["input"], res["expected"], res["got"])
                except Exception:
                    cand = None
                if cand:
                    ok, why = leakcheck.check(cand, p, 2)
                    st.log_model("explain_counterexample", ok, ",".join(why))
                    expl = cand if ok else None
            if not expl:
                expl = " ".join(EXPLAIN[f] for f in res["features"][:1] if f in EXPLAIN) or \
                       "Trace your program by hand on this input and compare with the expected output."
            res["explanation"] = expl
        elif res["status"] == "none_found":
            res["note"] = (f"No failing input found in {res['tests_run']} tests. That is evidence, not proof. "
                           "Finish the session and re-solve it closed-book later.")
        return res

    @app.post("/api/sessions/{sid}/finish")
    def finish(sid: int, b: Finish):
        row = sess_or_404(sid)
        if row["finished"]:
            raise HTTPException(400, "already finished")
        outcome = (scheduler.INDEPENDENT if row["hints_used"] == 0 else scheduler.HINTED) if b.solved \
            else scheduler.NOT_SOLVED
        st.finish_session(sid, outcome)
        now = time.time()
        iv = s.review_intervals_days
        if row["review_id"]:
            rv = st.review(row["review_id"])
            st.complete_review(rv["id"], outcome)
            stage, due = scheduler.after_review(rv["stage"], outcome, now, iv)
        else:
            stage, due = 0, scheduler.first_due(now, iv)
        if due is not None:
            st.add_review(row["learner"], row["problem_id"], stage, due)
        profile = metrics.learner_stats(st, row["learner"])["failure_profile"]
        return {"outcome": outcome, "next_review_in_days": None if due is None else round((due - now) / 86400, 1),
                "mistake_profile": profile}

    @app.get("/api/reviews/due")
    def due(learner: str):
        return {"due": st.due_reviews(learner), "upcoming": st.upcoming_reviews(learner)}

    @app.get("/api/stats")
    def stats(learner: str):
        return {"learner": metrics.learner_stats(st, learner), "model": metrics.model_stats(st)}

    if s.dev_mode:
        @app.post("/api/dev/shift")
        def shift(b: Shift):
            st.shift_reviews(b.learner, b.days)
            return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
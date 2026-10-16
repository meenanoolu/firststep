import dataclasses
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.llm import FakeClient
from eval.solutions import SOLUTIONS

BUGGY = "n=int(input());a=list(map(int,input().split()))\nb=c=0\nfor x in a:\n    c=max(0,c+x);b=max(b,c)\nprint(b)\n"
L = "learner-123"


def mk(llm=None, **kw):
    s = dataclasses.replace(Settings(), db_path=":memory:", dev_mode=True, **kw)
    return TestClient(create_app(s, llm=llm))


def test_full_flow_and_review_ladder():
    c = mk()
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "max-subarray"}).json()["session_id"]
    fs = c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would try all blocks with two loops and keep the best"}).json()
    assert fs["viable"]
    r = c.post(f"/api/sessions/{sid}/submit", json={"code": BUGGY}).json()
    assert r["status"] == "found" and "all_negative" in r["features"] and r["explanation"]
    assert "code" not in r
    h = c.post(f"/api/sessions/{sid}/hint").json()
    assert h["level"] == 1
    # hint 2 requires another run
    assert c.post(f"/api/sessions/{sid}/hint").status_code == 429
    r2 = c.post(f"/api/sessions/{sid}/submit", json={"code": SOLUTIONS["max-subarray"]}).json()
    assert r2["status"] == "none_found"
    fin = c.post(f"/api/sessions/{sid}/finish", json={"solved": True}).json()
    assert fin["outcome"] == "hinted" and fin["next_review_in_days"] == 1.0
    assert "all_negative" in fin["mistake_profile"]
    assert c.get("/api/reviews/due", params={"learner": L}).json()["due"] == []
    c.post("/api/dev/shift", json={"learner": L, "days": 2})
    due = c.get("/api/reviews/due", params={"learner": L}).json()["due"]
    assert len(due) == 1
    s2 = c.post("/api/sessions", json={"learner": L, "problem_id": "max-subarray", "review_id": due[0]["id"]}).json()["session_id"]
    f2 = c.post(f"/api/sessions/{s2}/finish", json={"solved": True}).json()
    assert f2["outcome"] == "independent" and f2["next_review_in_days"] == 3.0
    st = c.get("/api/stats", params={"learner": L}).json()["learner"]
    assert st["unaided_restart_rate"] == 1.0


def test_daily_cap():
    c = mk(max_submits_per_day=1)
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "longest-equal-run"}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would work a small example by hand with 3 numbers, like 1 2 3"})
    assert c.post(f"/api/sessions/{sid}/submit", json={"code": "print(1)"}).status_code == 200
    assert c.post(f"/api/sessions/{sid}/submit", json={"code": "print(1)"}).status_code == 429


def test_leaky_model_explanation_discarded():
    c = mk(llm=FakeClient("The answer is:\n```python\nprint(1)\n```"))
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "max-subarray"}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would work a small example by hand with 3 numbers, like 1 2 3"})
    r = c.post(f"/api/sessions/{sid}/submit", json={"code": BUGGY}).json()
    assert "```" not in r["explanation"]
    m = c.get("/api/stats", params={"learner": L}).json()["model"]
    assert m["explain_counterexample"]["rejected"] == 1


def test_bad_inputs():
    c = mk()
    assert c.post("/api/sessions", json={"learner": L, "problem_id": "nope"}).status_code == 404
    assert c.get("/api/problems/nope").status_code == 404
    assert c.post("/api/sessions/999/hint").status_code == 404
    assert c.get("/api/health").json()["ok"]


def test_payment_link_https_only():
    assert mk(payment_url="https://paypal.me/x").get("/api/config").json()["payment_url"] == "https://paypal.me/x"
    assert mk(payment_url="javascript:alert(1)").get("/api/config").json()["payment_url"] == ""


def test_model_calls_work_with_tracing_noop():
    from app.llm import FakeClient
    c = FakeClient("Which input is the smallest one your code could fail on?")
    assert c.rephrase_hint("s", "h", 1)
    from app import observability
    assert observability.init() is False  # no DSN in tests

def test_submit_requires_viable_first_step():
    c = mk()
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "max-subarray"}).json()["session_id"]
    assert c.post(f"/api/sessions/{sid}/submit", json={"code": "print(0)"}).status_code == 403
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "do it"})
    assert c.post(f"/api/sessions/{sid}/submit", json={"code": "print(0)"}).status_code == 403
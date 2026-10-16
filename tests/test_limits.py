import dataclasses

from fastapi.testclient import TestClient

from app.config import Settings
from app.limits import Limiter
from app.main import create_app

CODE = "unlock-code-123456"


def mk(**kw):
    return TestClient(create_app(dataclasses.replace(Settings(), db_path=":memory:", **kw), llm=None))


def session(c, learner):
    sid = c.post("/api/sessions", json={"learner": learner, "problem_id": "longest-equal-run"}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would work a small example by hand with 3 numbers, like 1 2 3"})
    return sid


def test_limiter_window():
    lim = Limiter()
    for t in (0, 1, 2):
        lim.record("k", 10, now=t)
    assert lim.blocked("k", 3, 10, now=3)
    assert not lim.blocked("k", 3, 10, now=20)      # old hits expire


def test_runs_are_capped_per_address_not_just_per_learner_id():
    c = mk(max_submits_per_ip_per_day=2)
    h = {"x-forwarded-for": "9.9.9.9"}
    codes = [c.post(f"/api/sessions/{session(c, f'learner-{i}-aaaa')}/submit", json={"code": "print(1)"}, headers=h).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]                  # three different learner ids, one address
    other = {"x-forwarded-for": "8.8.8.8"}
    assert c.post(f"/api/sessions/{session(c, 'learner-9-aaaa')}/submit", json={"code": "print(1)"}, headers=other).status_code == 200


def test_spoofed_leading_forwarded_for_entry_does_not_help():
    c = mk(max_submits_per_ip_per_day=1)
    h1 = {"x-forwarded-for": "1.1.1.1, 7.7.7.7"}
    h2 = {"x-forwarded-for": "2.2.2.2, 7.7.7.7"}     # attacker changes the first entry; the proxy-added last one is the same
    assert c.post(f"/api/sessions/{session(c, 'learner-1-aaaa')}/submit", json={"code": "print(1)"}, headers=h1).status_code == 200
    assert c.post(f"/api/sessions/{session(c, 'learner-2-aaaa')}/submit", json={"code": "print(1)"}, headers=h2).status_code == 429


def test_code_guessing_blocked_per_address_even_when_learner_ids_rotate():
    c = mk(pro_codes=(CODE,), max_code_failures_per_ip_per_hour=3)
    h = {"x-forwarded-for": "5.5.5.5"}
    for i in range(3):
        assert c.post("/api/pro/redeem", json={"learner": f"rotating-{i}-aaaa", "code": "wrong-code-xyz"}, headers=h).status_code == 400
    assert c.post("/api/pro/redeem", json={"learner": "rotating-9-aaaa", "code": CODE}, headers=h).status_code == 429
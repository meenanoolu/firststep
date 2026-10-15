import dataclasses
import sqlite3

from fastapi.testclient import TestClient

from app import metrics
from app.config import Settings
from app.main import create_app
from app.runner import Program
from app.store import Store
from eval.solutions import SOLUTIONS

BUGGY = "n=int(input());a=list(map(int,input().split()))\nb=c=0\nfor x in a:\n    c=max(0,c+x);b=max(b,c)\nprint(b)\n"
L = "learner-report-1"


def mk(**kw):
    s = dataclasses.replace(Settings(), db_path=":memory:", dev_mode=True, **kw)
    return TestClient(create_app(s, llm=None))


def play(c, pid="max-subarray", code=BUGGY, solved=True, review_id=None):
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": pid, "review_id": review_id}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would try all blocks with two loops and keep the best"})
    c.post(f"/api/sessions/{sid}/submit", json={"code": code})
    return c.post(f"/api/sessions/{sid}/finish", json={"solved": solved}).json()


def test_report_empty_learner():
    r = mk().get("/api/report", params={"learner": "nobody-here"}).json()
    assert r["sessions"] == 0 and r["problems"] == [] and r["streak_days"] == 0


def test_report_after_session_and_ladder():
    c = mk()
    play(c)
    r = c.get("/api/report", params={"learner": L}).json()
    assert r["sessions"] == 1 and r["streak_days"] == 1
    assert r["failure_profile"].get("all_negative") == 1
    p = r["problems"][0]
    assert p["problem_id"] == "max-subarray" and p["status"] == "waiting" and p["rungs_done"] == 0
    assert r["history"][0]["broke_on"] and r["history"][0]["first_step"] in ("brute_force", "small_example")
    c.post("/api/dev/shift", json={"learner": L, "days": 2})
    assert c.get("/api/report", params={"learner": L}).json()["due_now"] == 1


def test_ladder_completes_to_mastered():
    c = mk(review_intervals_days=(1, 3))
    play(c, code=SOLUTIONS["max-subarray"])
    for _ in range(2):
        c.post("/api/dev/shift", json={"learner": L, "days": 5})
        rid = c.get("/api/reviews/due", params={"learner": L}).json()["due"][0]["id"]
        play(c, code=SOLUTIONS["max-subarray"], review_id=rid)
    p = c.get("/api/report", params={"learner": L}).json()["problems"][0]
    assert p["status"] == "mastered" and p["rungs_done"] == p["ladder_len"] == 2


def _stored_text(tmp_path, flag):
    path = str(tmp_path / f"fs{int(flag)}.db")
    s = dataclasses.replace(Settings(), db_path=path, store_first_steps=flag)
    c = TestClient(create_app(s, llm=None))
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "max-subarray"}).json()["session_id"]
    c.post(f"/api/sessions/{sid}/first-step", json={"text": "I would try all blocks with two loops"})
    return sqlite3.connect(path).execute("SELECT first_step_text FROM sessions WHERE id=?", (sid,)).fetchone()[0]


def test_first_step_text_saved_and_optional(tmp_path):
    assert _stored_text(tmp_path, True) == "I would try all blocks with two loops"
    assert _stored_text(tmp_path, False) is None


def test_streak_logic():
    assert metrics._streak({10, 9, 8}, 10) == 3
    assert metrics._streak({9, 8}, 10) == 2      # not lost before practising today
    assert metrics._streak({7}, 10) == 0


def test_store_migrates_old_db(tmp_path):
    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE sessions(id INTEGER PRIMARY KEY, learner TEXT, problem_id TEXT, review_id INTEGER, "
               "created REAL, first_step_ts REAL, first_step_cat TEXT, hints_used INTEGER DEFAULT 0, finished REAL, outcome TEXT)")
    db.commit(); db.close()
    st = Store(path)
    sid = st.new_session("abcdef", "max-subarray")
    st.set_first_step(sid, "brute_force", "try everything")
    assert st.session(sid)["first_step_text"] == "try everything"


def test_report_page_served():
    assert "FirstStep session report" in mk().get("/report").text


def _verdict(lang, code):
    with Program.prepare(lang, code) as p:
        return p.verdict


def test_runner_blocks_common_escapes():
    assert _verdict("python", "print(getattr(__builtins__, 'open'))") == "REJECTED"
    assert _verdict("python", "import io\nprint(1)") == "REJECTED"
    assert _verdict("python", "import sys\nprint(sys.modules)") == "REJECTED"
    assert _verdict("python", "import sys\nprint(len(sys.stdin.read().split()))") == "OK"
    assert _verdict("cpp", '#include <bits/stdc++.h>\nint main(){int f=open("/proc/1/environ",0);}') == "REJECTED"
    assert _verdict("cpp", "#include <unistd.h>\nint main(){}") == "REJECTED"
    assert _verdict("cpp", "#include <bits/stdc++.h>\nint main(){int n;std::cin>>n;std::cout<<n;}") == "OK"
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


# ---------------------------------------------------------------- paid full report
from app import pro  # noqa: E402

CODE = "unlock-code-123456"


def test_report_locked_until_code_redeemed():
    c = mk(pro_codes=(CODE,))
    play(c)
    assert c.get("/api/config").json()["pro_enabled"] is True
    assert c.get("/api/report", params={"learner": L}).json()["pro"] is None
    assert c.post("/api/pro/redeem", json={"learner": L, "code": "wrong-code-0000"}).status_code == 400
    assert c.post("/api/pro/redeem", json={"learner": L, "code": CODE}).json() == {"pro": True}
    assert c.get("/api/pro/status", params={"learner": L}).json() == {"pro": True}
    r = c.get("/api/report", params={"learner": L}).json()["pro"]
    assert r["trend"][0]["sessions"] == 1 and r["first_steps"][0]["text"].startswith("I would try all blocks")
    assert r["next_up"], "a learner who failed on all_negative gets a practice plan"


def test_code_moves_to_the_newest_device_and_guard_blocks_guessing():
    c = mk(pro_codes=(CODE,))
    assert c.post("/api/pro/redeem", json={"learner": L, "code": CODE}).status_code == 200
    assert c.post("/api/pro/redeem", json={"learner": L, "code": CODE}).status_code == 200  # same learner again is fine
    assert c.post("/api/pro/redeem", json={"learner": "new-browser-1", "code": CODE}).status_code == 200
    assert c.get("/api/pro/status", params={"learner": "new-browser-1"}).json() == {"pro": True}
    assert c.get("/api/pro/status", params={"learner": L}).json() == {"pro": False}   # one code, one active holder
    for _ in range(8):
        c.post("/api/pro/redeem", json={"learner": "guesser-0001", "code": "nope-nope-nope"})
    assert c.post("/api/pro/redeem", json={"learner": "guesser-0001", "code": CODE}).status_code == 429


def test_no_codes_configured_means_nothing_unlocks():
    c = mk()
    assert c.get("/api/config").json()["pro_enabled"] is False
    assert c.post("/api/pro/redeem", json={"learner": L, "code": "anything-long-enough"}).status_code == 400


def test_gumroad_verification_logic():
    s = dataclasses.replace(Settings(), gumroad_product_id="prod123")
    class R:
        def __init__(self, j): self.j = j
        def json(self): return self.j
    ok = lambda *a, **k: R({"success": True, "purchase": {"refunded": False, "chargebacked": False}})
    refunded = lambda *a, **k: R({"success": True, "purchase": {"refunded": True}})
    bad = lambda *a, **k: R({"success": False})
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network"))
    assert pro.code_is_valid(s, "LICENSE-KEY-1234", post=ok)
    assert not pro.code_is_valid(s, "LICENSE-KEY-1234", post=refunded)
    assert not pro.code_is_valid(s, "LICENSE-KEY-1234", post=bad)
    assert not pro.code_is_valid(s, "LICENSE-KEY-1234", post=boom)


def test_next_up_ranks_by_mistakes_and_skips_mastered():
    feats = pro.problem_features()
    assert "all_negative" in feats["max-subarray"]
    plan = pro.next_up({"all_negative": 3}, {}, {"max-subarray": "Best stretch"})
    assert plan and plan[0]["problem_id"] == "max-subarray"
    assert pro.next_up({"all_negative": 3}, {"max-subarray": "mastered"}, {}) == []


# ---------------------------------------------------------------- paid problem pack
def test_pro_problems_are_locked_until_unlocked():
    c = mk(pro_codes=(CODE,))
    listing = {p["id"]: p for p in c.get("/api/problems", params={"learner": L}).json()}
    assert listing["longest-fresh-stretch"]["locked"] and listing["exact-target-blocks"]["locked"]
    assert not listing["max-subarray"]["locked"]
    assert c.get("/api/problems/longest-fresh-stretch", params={"learner": L}).status_code == 402
    assert c.get("/api/problems/longest-fresh-stretch").status_code == 402          # no learner at all
    assert c.post("/api/sessions", json={"learner": L, "problem_id": "exact-target-blocks"}).status_code == 402
    assert c.get("/api/problems/max-subarray").status_code == 200                    # free stays free
    c.post("/api/pro/redeem", json={"learner": L, "code": CODE})
    assert c.get("/api/problems/longest-fresh-stretch", params={"learner": L}).status_code == 200
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "exact-target-blocks"}).json()["session_id"]
    assert sid
    other = {p["id"]: p for p in c.get("/api/problems", params={"learner": "other-learner"}).json()}
    assert other["exact-target-blocks"]["locked"]                                     # unlock is per learner


def test_pro_problem_full_session_finds_the_classic_bug():
    c = mk(pro_codes=(CODE,))
    c.post("/api/pro/redeem", json={"learner": L, "code": CODE})
    sid = c.post("/api/sessions", json={"learner": L, "problem_id": "exact-target-blocks"}).json()["session_id"]
    buggy = ("n,k=map(int,input().split());a=list(map(int,input().split()))\nseen={};s=0;t=0\nfor x in a:\n"
             "    s+=x\n    t+=seen.get(s-k,0)\n    seen[s]=seen.get(s,0)+1\nprint(t)\n")
    r = c.post(f"/api/sessions/{sid}/submit", json={"code": buggy}).json()
    assert r["status"] == "found" and "starts_at_first" in r["features"]
    assert c.post(f"/api/sessions/{sid}/hint").json()["level"] == 1

"""SQLite store. One connection guarded by a lock; fine for a small deployment."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, learner TEXT, problem_id TEXT, review_id INTEGER, created REAL,
  first_step_ts REAL, first_step_cat TEXT, hints_used INTEGER DEFAULT 0, finished REAL, outcome TEXT);
CREATE TABLE IF NOT EXISTS submissions(
  id INTEGER PRIMARY KEY, session_id INTEGER, learner TEXT, ts REAL, language TEXT, code TEXT,
  status TEXT, features TEXT, tests_run INTEGER, size_before INTEGER, size_after INTEGER);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY, learner TEXT, problem_id TEXT, stage INTEGER, due_ts REAL, done_ts REAL, outcome TEXT);
CREATE TABLE IF NOT EXISTS pro_unlocks(
  code_hash TEXT PRIMARY KEY, learner TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS model_calls(
  id INTEGER PRIMARY KEY, ts REAL, job TEXT, accepted INTEGER, reason TEXT);
"""


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            cols = {r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")}
            if "first_step_text" not in cols:  # migrate DBs created before real first-step capture
                self.db.execute("ALTER TABLE sessions ADD COLUMN first_step_text TEXT")
                self.db.commit()

    def _x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def one(self, sql, args=()):
        with self.lock:
            r = self.db.execute(sql, args).fetchone()
        return dict(r) if r else None

    def all(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # sessions
    def new_session(self, learner, problem_id, review_id=None) -> int:
        return self._x("INSERT INTO sessions(learner,problem_id,review_id,created) VALUES(?,?,?,?)",
                       (learner, problem_id, review_id, time.time())).lastrowid

    def session(self, sid):
        return self.one("SELECT * FROM sessions WHERE id=?", (sid,))

    def set_first_step(self, sid, cat, text=None):
        self._x("UPDATE sessions SET first_step_ts=?, first_step_cat=?, first_step_text=? WHERE id=?",
                (time.time(), cat, text, sid))

    def bump_hint(self, sid):
        self._x("UPDATE sessions SET hints_used=hints_used+1 WHERE id=?", (sid,))

    def finish_session(self, sid, outcome):
        self._x("UPDATE sessions SET finished=?, outcome=? WHERE id=?", (time.time(), outcome, sid))

    # submissions
    def add_submission(self, sid, learner, language, code, status, features, tests_run, before, after):
        self._x("INSERT INTO submissions(session_id,learner,ts,language,code,status,features,tests_run,"
                "size_before,size_after) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sid, learner, time.time(), language, code, status, json.dumps(features), tests_run, before, after))

    def submissions_in_session(self, sid) -> int:
        return self.one("SELECT COUNT(*) c FROM submissions WHERE session_id=?", (sid,))["c"]

    def submissions_last_day(self, learner) -> int:
        return self.one("SELECT COUNT(*) c FROM submissions WHERE learner=? AND ts>?",
                        (learner, time.time() - 86400))["c"]

    # reviews
    def add_review(self, learner, problem_id, stage, due_ts) -> int:
        return self._x("INSERT INTO reviews(learner,problem_id,stage,due_ts) VALUES(?,?,?,?)",
                       (learner, problem_id, stage, due_ts)).lastrowid

    def review(self, rid):
        return self.one("SELECT * FROM reviews WHERE id=?", (rid,))

    def due_reviews(self, learner, now=None):
        return self.all("SELECT * FROM reviews WHERE learner=? AND done_ts IS NULL AND due_ts<=? ORDER BY due_ts",
                        (learner, now or time.time()))

    def upcoming_reviews(self, learner):
        return self.all("SELECT * FROM reviews WHERE learner=? AND done_ts IS NULL ORDER BY due_ts", (learner,))

    def complete_review(self, rid, outcome):
        self._x("UPDATE reviews SET done_ts=?, outcome=? WHERE id=?", (time.time(), outcome, rid))

    def shift_reviews(self, learner, days):
        self._x("UPDATE reviews SET due_ts=due_ts-? WHERE learner=? AND done_ts IS NULL", (days * 86400, learner))

    # model calls
    def log_model(self, job, accepted, reason=""):
        self._x("INSERT INTO model_calls(ts,job,accepted,reason) VALUES(?,?,?,?)",
                (time.time(), job, int(accepted), reason))

    # paid report unlocks (the code itself is never stored, only its hash)
    def unlock_owner(self, code_hash):
        r = self.one("SELECT learner FROM pro_unlocks WHERE code_hash=?", (code_hash,))
        return r["learner"] if r else None

    def add_unlock(self, code_hash, learner):
        self._x("INSERT OR IGNORE INTO pro_unlocks(code_hash,learner,ts) VALUES(?,?,?)", (code_hash, learner, time.time()))

    def is_pro(self, learner) -> bool:
        return self.one("SELECT 1 x FROM pro_unlocks WHERE learner=?", (learner,)) is not None

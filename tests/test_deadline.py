import time

from app.counterexample import find_counterexample
from app.problems import PROBLEMS
from eval.solutions import SOLUTIONS

SLOW = "import time\ntime.sleep(0.05)\n" + SOLUTIONS["longest-equal-run"]


def test_slow_but_correct_program_is_cut_off():
    t0 = time.monotonic()
    r = find_counterexample(PROBLEMS["longest-equal-run"], "python", SLOW, deadline_s=0.4)
    assert r["status"] == "too_slow" and r["tests_run"] >= 1
    assert time.monotonic() - t0 < 3


def test_fast_program_unaffected_by_deadline():
    r = find_counterexample(PROBLEMS["longest-equal-run"], "python", SOLUTIONS["longest-equal-run"], deadline_s=30)
    assert r["status"] == "none_found"

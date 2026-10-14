import pytest
from app import leakcheck, scheduler, firststep
from app.hints import get_hint
from app.problems import PROBLEMS

P = PROBLEMS["max-subarray"]


def test_all_static_hints_pass_leakcheck():
    for p in PROBLEMS.values():
        for lvl, h in enumerate(p.hints, 1):
            ok, why = leakcheck.check(h, p, lvl)
            assert ok, (p.id, lvl, why)


@pytest.mark.parametrize("text,lvl", [
    ("Use this:\n```python\nprint(1)\n```", 1),
    ("The answer is to use kadane", 4),
    ("best = cur = a[0]\nfor x in a[1:]:", 4),
    ("Try Kadane's algorithm here.", 2),
    ("cur = max(x, cur + x) then best = max(best, cur)", 4),
])
def test_leaks_caught(text, lvl):
    ok, why = leakcheck.check(text, P, lvl)
    assert not ok and why


def test_model_leak_discarded_and_static_used():
    class Leaky:
        def rephrase_hint(self, s, h, l): return "The answer is:\n```\nprint(1)\n```"
    r = get_hint(P, 2, Leaky())
    assert r["source"] == "static" and r["rejected"] and r["text"] == P.hints[1]


def test_model_clean_rephrase_accepted():
    class Clean:
        def rephrase_hint(self, s, h, l): return "What should the result be if every number is below zero?"
    assert get_hint(P, 1, Clean())["source"] == "model"


def test_scheduler_ladder():
    iv = (1, 3, 7, 21)
    assert scheduler.after_review(0, "independent", 0, iv) == (1, 3 * 86400)
    assert scheduler.after_review(2, "hinted", 0, iv) == (2, 7 * 86400)
    assert scheduler.after_review(2, "not_solved", 0, iv) == (0, 86400)
    assert scheduler.after_review(3, "independent", 0, iv) == (4, None)
    with pytest.raises(ValueError):
        scheduler.after_review(0, "x", 0, iv)


@pytest.mark.parametrize("text,cat", [
    ("ok", "too_vague"),
    ("choose a non-empty block of consecutive numbers with the largest possible sum", "restate"),
    ("I would try all blocks with two loops and keep the largest sum", "brute_force"),
    ("first I would work a small example by hand with negative numbers", "small_example"),
    ("I would keep track of the best sum ending at each position", "observation"),
])
def test_first_step_rules(text, cat):
    assert firststep.judge(P.statement, text)["category"] == cat


def test_first_step_model_label_must_be_valid():
    class Bad:
        def judge_first_step(self, s, t): return "genius"
    assert firststep.judge(P.statement, "ok", Bad())["source"] == "rules"

def test_concrete_numbers_count_as_small_example():
    t = "for l=2 and r=4, i would add a[l] to sum then a[l+1] to sum and till a[r] to sum"
    r = firststep.judge(PROBLEMS["range-sum-queries"].statement, t)
    assert r["viable"] and r["category"] == "small_example"
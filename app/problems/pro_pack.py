"""Paid problem pack: two harder (level 3) problems. Same structure as the free bank: a trusted fast solution,
an independent brute force, hand-written graded hints, and samples that do NOT trigger the classic pitfall."""
from __future__ import annotations

from .bank import _n
from .base import Problem, fmt_list, list_shrinks


# ---------------------------------------------------------------- 1. longest block with no repeated value
def _dw_solve(a):
    last, left, best = {}, 0, 0
    for i, x in enumerate(a):
        if x in last:
            left = max(left, last[x] + 1)
        last[x] = i
        best = max(best, i - left + 1)
    return str(best)


def _dw_brute(a):
    n = len(a)
    return str(max(j - i + 1 for i in range(n) for j in range(i, n) if len(set(a[i:j + 1])) == j - i + 1))


def _dw_features(a):
    last, left, stale, lens = {}, 0, False, []
    for i, x in enumerate(a):
        if x in last:
            if last[x] < left:
                stale = True          # a repeat whose earlier copy already left the block
            else:
                left = last[x] + 1
        last[x] = i
        lens.append(i - left + 1)
    f = []
    if len(a) == 1:
        f.append("single_element")
    if len(set(a)) == 1:
        f.append("all_equal")
    if stale:
        f.append("stale_repeat")
    if lens[-1] < max(lens):
        f.append("best_not_at_end")
    return f


FRESH_STRETCH = Problem(
    id="longest-fresh-stretch", title="Longest fresh stretch", difficulty=3, tags=("arrays", "two-pointers"),
    statement="Given n integers, find the length of the longest block of consecutive numbers in which no value "
              "appears twice.",
    input_format="Line 1: n. Line 2: n integers.", output_format="One integer.",
    constraints="1 <= n <= 100000.",
    samples=(("6\n1 2 3 1 2 3\n", "3"), ("5\n4 4 5 6 4\n", "3")),
    gen=lambda rng, i: [rng.randint(1, 4) for _ in range(_n(i))],
    edge_cases=lambda: [[7], [1, 1], [1, 2, 3], [1, 2, 2, 1], [1, 2, 3, 3], [2, 1, 1, 2, 3]],
    shrinks=lambda c: list_shrinks(c),
    fmt=fmt_list, solve=_dw_solve, brute=_dw_brute, features=_dw_features, size=len,
    hints=(
        "Think about a number that appears again, but whose earlier copy is already outside the block you are "
        "currently building. Does your program treat that earlier copy as still inside?",
        "Checking every block is far too slow for 100000 numbers. As you walk to the right, what is the leftmost "
        "position your block is still allowed to start at?",
        "Remember where each value was last seen. When a value repeats, the block must start after its previous "
        "position, but it must never start earlier than it already does. Compare the length after every step.",
        "Structure: keep the current start and the best length; for each position, if its value was seen before, "
        "move the start forward only when that earlier position is at or after the start; record the position; "
        "update the best with the current length; print the best.",
    ),
    rubric="A viable first step: check every block with a set (slow but correct), or work a tiny list by hand and "
           "notice the block can only grow to the right until a value repeats.",
    spoilers={"sliding window": 3, "two pointers": 3, "last[": 5, "max(left": 5, "left =": 5},
    reference_src="last = {}\nleft = best = 0\nfor i, x in enumerate(a):\n    if x in last:\n        left = max(left, last[x] + 1)\n    last[x] = i\n    best = max(best, i - left + 1)\nprint(best)\n",
    tier="pro",
)


# ---------------------------------------------------------------- 2. count blocks with an exact sum (negatives allowed)
def _ss_solve(c):
    a, k = c
    seen, s, t = {0: 1}, 0, 0
    for x in a:
        s += x
        t += seen.get(s - k, 0)
        seen[s] = seen.get(s, 0) + 1
    return str(t)


def _ss_brute(c):
    a, k = c
    return str(sum(1 for i in range(len(a)) for j in range(i, len(a)) if sum(a[i:j + 1]) == k))


def _ss_gen(rng, i):
    return ([rng.randint(-3, 3) for _ in range(_n(i))], rng.randint(-3, 4))


def _ss_shrinks(c):
    a, k = c
    return [(x, k) for x in list_shrinks(a)]


def _ss_features(c):
    a, k = c
    f, s, first = [], 0, False
    for x in a:
        s += x
        first = first or s == k
    if any(x < 0 for x in a):
        f.append("has_negative")
    if 0 in a:
        f.append("has_zero")
    if first:
        f.append("starts_at_first")
    if len(a) == 1:
        f.append("single_element")
    return f


EXACT_TARGET = Problem(
    id="exact-target-blocks", title="Exactly on target", difficulty=3, tags=("arrays", "prefix-sums", "hashing"),
    statement="You are given n integers (they may be negative or zero) and a target k. Count the blocks of "
              "consecutive numbers whose sum is exactly k. Blocks at different positions count separately, even if "
              "they contain the same values.",
    input_format="Line 1: n and k. Line 2: n integers.", output_format="One integer.",
    constraints="1 <= n <= 100000, |a_i| <= 10^9.",
    samples=(("5 5\n1 2 3 2 3\n", "3"), ("4 4\n2 1 3 1\n", "2")),
    gen=_ss_gen,
    edge_cases=lambda: [([3], 3), ([0], 0), ([1, 2, 3], 3), ([1, -1, 1], 0), ([0, 0, 0], 0), ([2, -2, 2], 2)],
    shrinks=_ss_shrinks,
    fmt=lambda c: f"{len(c[0])} {c[1]}\n{' '.join(map(str, c[0]))}\n",
    solve=_ss_solve, brute=_ss_brute, features=_ss_features, size=lambda c: len(c[0]),
    hints=(
        "Try a list with a zero or a negative number in it. Does your program still count every block, or does it "
        "assume the numbers only grow?",
        "Checking every block is too slow for 100000 numbers. Is there a number you could compute once per position "
        "so that the sum of ANY block becomes a single subtraction?",
        "A block ends at the current position when the total so far minus some earlier total equals k. So at each "
        "position you need to know how many earlier totals equal (total so far minus k). What should you remember, "
        "and how often? And which 'earlier total' stands for a block that starts at the very first number?",
        "Structure: keep a tally of how many times each running total has appeared, starting with the empty total 0 "
        "counted once; for each number, update the running total, add the tally of (running total minus k) to the "
        "answer, then count the new running total; print the answer.",
    ),
    rubric="A viable first step: sum every block with two loops (slow but correct), or notice that a block sum is a "
           "difference of two running totals.",
    spoilers={"hash": 3, "dictionary": 3, "prefix": 3, "defaultdict": 5, "seen[": 5, "seen.get": 5, "count[0]": 5},
    reference_src="seen = {0: 1}\ns = t = 0\nfor x in a:\n    s += x\n    t += seen.get(s - k, 0)\n    seen[s] = seen.get(s, 0) + 1\nprint(t)\n",
    tier="pro",
)

PRO_PROBLEMS = {p.id: p for p in (FRESH_STRETCH, EXACT_TARGET)}

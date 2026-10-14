"""Six original beginner problems. Samples deliberately do NOT trigger the classic pitfall,
so a solution can pass every sample and still be wrong - that is the point of the finder."""
from __future__ import annotations

from .base import Problem, fmt_list, list_shrinks


def _n(i: int) -> int:
    return 1 + min(i // 12, 7)


# ---------------------------------------------------------------- 1. max subarray
def _ms_solve(a):
    best = cur = a[0]
    for x in a[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return str(best)


def _ms_brute(a):
    return str(max(sum(a[i:j + 1]) for i in range(len(a)) for j in range(i, len(a))))


MAX_SUBARRAY = Problem(
    id="max-subarray", title="Best stretch", difficulty=2, tags=("arrays", "dp"),
    statement="You are given n integers (they may be negative). Choose a non-empty block of consecutive "
              "numbers with the largest possible sum and print that sum.",
    input_format="Line 1: n. Line 2: n integers.", output_format="One integer.",
    constraints="1 <= n <= 100000, |a_i| <= 10^9.",
    samples=(("5\n1 -2 3 4 -1\n", "7"), ("4\n2 3 -1 4\n", "8")),
    gen=lambda rng, i: [rng.randint(-10, 10) for _ in range(_n(i))],
    edge_cases=lambda: [[-5], [-3, -1, -2], [0], [5], [-1, -1], [0, -1]],
    shrinks=lambda c: list_shrinks(c),
    fmt=fmt_list, solve=_ms_solve, brute=_ms_brute,
    features=lambda c: [f for f, ok in (("all_negative", max(c) < 0), ("single_element", len(c) == 1),
                                         ("has_zero", 0 in c)) if ok],
    size=len,
    hints=(
        "Ask what the answer is when every number is negative. Does your program agree?",
        "Think about the best block that ENDS at each position. What does it depend on?",
        "For each position keep two things: the best block ending here, and the best seen anywhere so far. "
        "Think carefully about what value each starts with.",
        "Structure: read the list; set both running values from the first element; loop over the rest, "
        "updating the block ending here (extend or restart), then the overall best; print the best.",
    ),
    rubric="A viable first step: brute force over all blocks, a small example (e.g. all negatives), "
           "or the observation that the answer depends on the best block ending at each index.",
    spoilers={"kadane": 4, "dynamic programming": 4, "max(x, cur": 5, "cur + x": 5, "ending here": 2},
    reference_src="best = cur = a[0]\nfor x in a[1:]:\n    cur = max(x, cur + x)\n    best = max(best, cur)\nprint(best)\n",
)


# ---------------------------------------------------------------- 2. count pairs
def _cp_solve(c):
    a, k = c
    seen: dict = {}
    total = 0
    for x in a:
        total += seen.get(k - x, 0)
        seen[x] = seen.get(x, 0) + 1
    return str(total)


def _cp_brute(c):
    a, k = c
    return str(sum(1 for i in range(len(a)) for j in range(i + 1, len(a)) if a[i] + a[j] == k))


def _cp_gen(rng, i):
    n = _n(i)
    return ([rng.randint(0, 5) for _ in range(n)], rng.randint(0, 10))


def _cp_shrinks(c):
    a, k = c
    out = [(x, k) for x in list_shrinks(a)]
    if k != 0:
        out.append((a, k // 2))
        out.append((a, k - (1 if k > 0 else -1)))
    return out


COUNT_PAIRS = Problem(
    id="count-pairs-sum", title="Pairs that add up", difficulty=2, tags=("arrays", "hashing"),
    statement="Given n integers and a target k, count pairs of DIFFERENT positions i < j with a_i + a_j = k. "
              "Equal values at different positions count as different pairs.",
    input_format="Line 1: n and k. Line 2: n integers.", output_format="One integer.",
    constraints="1 <= n <= 200000, |a_i|, |k| <= 10^9.",
    samples=(("4 5\n1 2 3 4\n", "2"), ("3 7\n3 4 5\n", "1")),
    gen=_cp_gen,
    edge_cases=lambda: [([2], 4), ([2, 2], 4), ([1, 1, 1], 2), ([3, 3, 3], 6), ([0, 0], 0)],
    shrinks=_cp_shrinks,
    fmt=lambda c: f"{len(c[0])} {c[1]}\n{' '.join(map(str, c[0]))}\n",
    solve=_cp_solve, brute=_cp_brute,
    features=lambda c: [f for f, ok in (
        ("self_pair_trap", any(2 * x == c[1] for x in c[0])),
        ("duplicates", len(set(c[0])) < len(c[0])),
        ("single_element", len(c[0]) == 1)) if ok],
    size=lambda c: len(c[0]),
    hints=(
        "Take [2] with k = 4. What should the answer be, and what does your program print?",
        "A number cannot pair with itself, but two equal numbers at different positions can. "
        "How does your code treat each case?",
        "Count each pair exactly once. Think about which earlier elements an element can pair with, "
        "and how many of them there are.",
        "Structure: walk the list left to right; before adding the current value, look up how many earlier "
        "values complete it to k; add that to the total; then record the current value; print the total.",
    ),
    rubric="A viable first step: double loop over i<j, a tiny example with equal values, or the observation "
           "that each element needs a partner k-x among earlier elements.",
    spoilers={"hash": 3, "dictionary": 3, "counter": 3, "seen": 4, "two pointers": 3},
    reference_src="seen = {}\ntotal = 0\nfor x in a:\n    total += seen.get(k - x, 0)\n    seen[x] = seen.get(x, 0) + 1\nprint(total)\n",
)


# ---------------------------------------------------------------- 3. longest equal run
def _lr_solve(a):
    best = run = 1
    for i in range(1, len(a)):
        run = run + 1 if a[i] == a[i - 1] else 1
        best = max(best, run)
    return str(best)


def _lr_brute(a):
    best = 1
    for i in range(len(a)):
        j = i
        while j + 1 < len(a) and a[j + 1] == a[i]:
            j += 1
        best = max(best, j - i + 1)
    return str(best)


def _lr_features(a):
    runs, cur = [], 1
    for i in range(1, len(a)):
        if a[i] == a[i - 1]:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    out = []
    if len(a) == 1:
        out.append("single_element")
    if len(set(a)) == 1:
        out.append("all_equal")
    if runs[-1] == max(runs) and runs[-1] > 1 and runs.count(max(runs)) == 1:
        out.append("longest_run_at_end")
    return out


LONGEST_RUN = Problem(
    id="longest-equal-run", title="Longest streak", difficulty=1, tags=("arrays", "loops"),
    statement="Given n integers, find the length of the longest block of consecutive EQUAL numbers.",
    input_format="Line 1: n. Line 2: n integers.", output_format="One integer.",
    constraints="1 <= n <= 100000.",
    samples=(("6\n1 1 2 2 2 3\n", "3"), ("4\n7 7 1 2\n", "2")),
    gen=lambda rng, i: [rng.randint(1, 3) for _ in range(_n(i))],
    edge_cases=lambda: [[5], [1, 2, 3], [1, 1, 1], [1, 2, 2, 2], [2, 2, 2, 1]],
    shrinks=lambda c: list_shrinks(c),
    fmt=fmt_list, solve=_lr_solve, brute=_lr_brute, features=_lr_features, size=len,
    hints=(
        "Try a list with a single number, and a list whose longest streak is at the very end. "
        "What does your program print?",
        "You need to remember two numbers while walking the list. What are they?",
        "Keep the length of the current streak and the best streak so far. Decide exactly WHEN the best "
        "gets compared, so the final streak is not forgotten.",
        "Structure: start the current streak at 1; for each next element either extend or reset it; "
        "after every step keep the maximum; print the maximum.",
    ),
    rubric="A viable first step: walk the list with a current-streak counter, or write the answer by hand "
           "for a tiny list, or brute force from every start position.",
    spoilers={"sliding window": 3, "max(best": 5, "run + 1": 5},
    reference_src="best = run = 1\nfor i in range(1, n):\n    run = run + 1 if a[i] == a[i - 1] else 1\n    best = max(best, run)\nprint(best)\n",
)


# ---------------------------------------------------------------- 4. balanced brackets
def _bb_solve(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    st = []
    for ch in s:
        if ch in "([{":
            st.append(ch)
        else:
            if not st or st.pop() != pairs[ch]:
                return "NO"
    return "NO" if st else "YES"


def _bb_brute(s):
    prev = None
    while prev != s:
        prev = s
        for p in ("()", "[]", "{}"):
            s = s.replace(p, "")
    return "YES" if s == "" else "NO"


def _bb_gen(rng, i):
    n = _n(i) + rng.randint(0, 2)
    if rng.random() < 0.5:
        return "".join(rng.choice("()[]{}") for _ in range(n))
    # mostly balanced, then corrupted
    s = ""
    for _ in range(max(1, n // 2)):
        o, c = rng.choice(["()", "[]", "{}"])
        s = s[:len(s) // 2] + o + c + s[len(s) // 2:]
    if rng.random() < 0.6 and s:
        k = rng.randrange(len(s))
        s = s[:k] + rng.choice("()[]{}") + s[k + 1:]
    return s


def _bb_shrinks(s):
    out = []
    n = len(s)
    if n > 1:
        out += [s[:n // 2], s[n // 2:]]
        out += [s[:i] + s[i + 1:] for i in range(n)]
    return [x for x in out if x]


def _bb_features(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    f, st = [], []
    if s[0] in pairs:
        f.append("starts_with_closer")
    if len(s) % 2:
        f.append("odd_length")
    for ch in s:
        if ch in "([{":
            st.append(ch)
        elif not st:
            f.append("closer_on_empty")
            break
        elif st.pop() != pairs[ch]:
            f.append("wrong_type_closer")
            break
    else:
        if st:
            f.append("unclosed_opener")
    return f


BRACKETS = Problem(
    id="balanced-brackets", title="Do the brackets match?", difficulty=2, tags=("strings", "stack"),
    statement="A string contains only the characters ( ) [ ] { }. It is balanced if every opening bracket is "
              "closed by the same kind of bracket in the right order. Print YES if balanced, otherwise NO.",
    input_format="One line: the string.", output_format="YES or NO.",
    constraints="1 <= length <= 200000.",
    samples=(("(())\n", "YES"), ("(()\n", "NO")),
    gen=_bb_gen,
    edge_cases=lambda: [")", "(", ")(", "([)]", "{[]}", "(]"],
    shrinks=_bb_shrinks,
    fmt=lambda s: s + "\n", solve=_bb_solve, brute=_bb_brute, features=_bb_features, size=len,
    hints=(
        "Try the string ')' and the string ')('. What should the answer be? What does your code do?",
        "When you meet a closing bracket, which earlier opening bracket must it match?",
        "The most recent unmatched opener is the one that matters. Think about what to do when there is "
        "no opener left, and what to check at the very end.",
        "Structure: keep a pile of unmatched openers; push on an opener; on a closer, fail if the pile is "
        "empty or its top is the wrong kind, else remove the top; at the end the pile must be empty.",
    ),
    rubric="A viable first step: repeatedly delete matching neighbours by hand on a tiny string, "
           "or the observation that the latest opener must match the next closer.",
    spoilers={"stack": 3, "push": 4, "pop": 4, "append": 5},
    reference_src="st = []\nfor ch in s:\n    if ch in '([{':\n        st.append(ch)\n    else:\n        if not st or st.pop() != pairs[ch]:\n            print('NO')\n",
)


# ---------------------------------------------------------------- 5. range sum queries
def _rs_solve(c):
    a, qs = c
    pre = [0]
    for x in a:
        pre.append(pre[-1] + x)
    return "\n".join(str(pre[r] - pre[l - 1]) for l, r in qs)


def _rs_brute(c):
    a, qs = c
    return "\n".join(str(sum(a[l - 1:r])) for l, r in qs)


def _rs_gen(rng, i):
    n = _n(i)
    a = [rng.randint(-5, 9) for _ in range(n)]
    qs = []
    for _ in range(rng.randint(1, 3)):
        l = rng.randint(1, n)
        qs.append((l, rng.randint(l, n)))
    return (a, qs)


def _rs_fix(a, qs):
    n = len(a)
    out = []
    for l, r in qs:
        l = max(1, min(l, n))
        r = max(l, min(r, n))
        out.append((l, r))
    return out


def _rs_shrinks(c):
    a, qs = c
    out = []
    for x in list_shrinks(a):
        out.append((x, _rs_fix(x, qs)))
    if len(qs) > 1:
        out += [(a, qs[:i] + qs[i + 1:]) for i in range(len(qs))]
    for i, (l, r) in enumerate(qs):
        if r > l:
            out.append((a, qs[:i] + [(l, r - 1)] + qs[i + 1:]))
        if l > 1:
            out.append((a, qs[:i] + [(l - 1, r)] + qs[i + 1:]))
    return out


RANGE_SUM = Problem(
    id="range-sum-queries", title="Many sums", difficulty=2, tags=("arrays", "prefix-sums"),
    statement="Given n integers and q queries, each query gives positions l and r (1-indexed, l <= r). "
              "For each query print the sum of the numbers from position l to position r inclusive.",
    input_format="Line 1: n and q. Line 2: n integers. Then q lines: l r.", output_format="q lines, one sum each.",
    constraints="1 <= n, q <= 200000.",
    samples=(("5 2\n1 2 3 4 5\n2 4\n3 5\n", "9\n12"),),
    gen=_rs_gen,
    edge_cases=lambda: [([5], [(1, 1)]), ([1, 2, 3], [(1, 3)]), ([1, 2, 3], [(1, 1)]), ([1, 2, 3], [(2, 2)])],
    shrinks=_rs_shrinks,
    fmt=lambda c: f"{len(c[0])} {len(c[1])}\n{' '.join(map(str, c[0]))}\n" + "".join(f"{l} {r}\n" for l, r in c[1]),
    solve=_rs_solve, brute=_rs_brute,
    features=lambda c: [f for f, ok in (
        ("query_starts_at_1", any(l == 1 for l, _ in c[1])),
        ("single_element_query", any(l == r for l, r in c[1])),
        ("single_element", len(c[0]) == 1)) if ok],
    size=lambda c: len(c[0]) + len(c[1]),
    hints=(
        "Run your program on a query that starts at position 1. Check it by hand.",
        "If you answer each query by looping, how long does it take for many large queries? "
        "Is there something you can compute once up front?",
        "Precompute, for every position, the sum of everything up to it. Then a range is a difference of two "
        "such totals. Be careful which two, and what happens at the very start.",
        "Structure: build the running totals with a leading 0; for each query print total[r] minus "
        "total[l-1]; mind the 1-indexing.",
    ),
    rubric="A viable first step: sum each range with a loop, or notice that repeated work can be saved "
           "by precomputing running totals.",
    spoilers={"prefix": 3, "cumulative": 3, "pre[": 5, "pre[r]": 5},
    reference_src="pre = [0]\nfor x in a:\n    pre.append(pre[-1] + x)\nfor l, r in qs:\n    print(pre[r] - pre[l - 1])\n",
)


# ---------------------------------------------------------------- 6. second largest distinct
def _sl_solve(a):
    d = sorted(set(a))
    return str(d[-2]) if len(d) >= 2 else "NONE"


def _sl_brute(a):
    m = max(a)
    rest = [x for x in a if x < m]
    return str(max(rest)) if rest else "NONE"


SECOND_LARGEST = Problem(
    id="second-largest-distinct", title="Runner-up", difficulty=1, tags=("arrays",),
    statement="Given n integers, print the second largest DISTINCT value. If there are fewer than two "
              "distinct values, print NONE.",
    input_format="Line 1: n. Line 2: n integers.", output_format="One integer or NONE.",
    constraints="1 <= n <= 100000.",
    samples=(("5\n3 1 4 1 5\n", "4"), ("3\n10 20 30\n", "20")),
    gen=lambda rng, i: [rng.randint(-3, 5) for _ in range(_n(i))],
    edge_cases=lambda: [[5], [2, 2], [3, 3, 1], [1, 3, 3], [-1, -1, -2]],
    shrinks=lambda c: list_shrinks(c),
    fmt=fmt_list, solve=_sl_solve, brute=_sl_brute,
    features=lambda c: [f for f, ok in (
        ("single_element", len(c) == 1), ("all_equal", len(set(c)) == 1),
        ("max_repeated", c.count(max(c)) > 1)) if ok],
    size=len,
    hints=(
        "Try [3, 3, 1] and [2, 2]. What should be printed, and what does your program print?",
        "If the biggest value appears twice, is it also the runner-up? Re-read the statement.",
        "Think about what you track while scanning: the largest value, and the largest value that is "
        "strictly smaller than it. What should happen when you see the largest value again?",
        "Structure: track the top value and the best value strictly below it; update both in one pass, "
        "ignoring repeats of the top; print NONE if nothing strictly below was ever seen.",
    ),
    rubric="A viable first step: sort and de-duplicate, or scan twice (find max, then max of the rest), "
           "or a tiny example with repeated maximum.",
    spoilers={"set(": 4, "sorted(": 4, "second = ": 5},
    reference_src="d = sorted(set(a))\nprint(d[-2] if len(d) >= 2 else 'NONE')\n",
)


PROBLEMS = {p.id: p for p in (LONGEST_RUN, SECOND_LARGEST, MAX_SUBARRAY, COUNT_PAIRS, BRACKETS, RANGE_SUM)}
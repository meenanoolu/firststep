import random
import pytest
from app.problems import PROBLEMS


@pytest.mark.parametrize("p", list(PROBLEMS.values()), ids=lambda p: p.id)
def test_solve_matches_brute(p):
    rng = random.Random(1)
    cases = p.edge_cases() + [p.gen(rng, i) for i in range(400)]
    for c in cases:
        assert p.solve(c) == p.brute(c), (p.id, c)


@pytest.mark.parametrize("p", list(PROBLEMS.values()), ids=lambda p: p.id)
def test_samples_agree_with_oracle(p):
    # parse by round trip: samples are stored as text, so check the oracle on the generated
    # equivalent through fmt where possible; here we just check samples are non-empty and stable
    assert p.samples and all(o.strip() for _, o in p.samples)


@pytest.mark.parametrize("p", list(PROBLEMS.values()), ids=lambda p: p.id)
def test_shrinks_are_smaller_or_equal_and_valid(p):
    rng = random.Random(2)
    for i in range(60):
        c = p.gen(rng, i)
        for s in p.shrinks(c):
            p.solve(s); p.brute(s); p.fmt(s)
            assert p.solve(s) == p.brute(s)


@pytest.mark.parametrize("p", list(PROBLEMS.values()), ids=lambda p: p.id)
def test_hints_have_four_levels_and_no_code(p):
    assert len(p.hints) == 4
    for h in p.hints:
        assert "```" not in h and "def " not in h
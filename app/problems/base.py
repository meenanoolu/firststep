"""Problem definition. Every problem carries a trusted solution AND an independent brute force,
so the oracle itself can be cross-checked (see tests/test_problems.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    difficulty: int                      # 1 (easiest) .. 3
    tags: tuple[str, ...]
    statement: str
    input_format: str
    output_format: str
    constraints: str
    samples: tuple[tuple[str, str], ...]  # (stdin, stdout); deliberately NOT containing the pitfall
    gen: Callable[[Any, int], Any]        # gen(rng, i) -> case, small sizes first
    edge_cases: Callable[[], list]
    shrinks: Callable[[Any], list]
    fmt: Callable[[Any], str]             # case -> stdin text
    solve: Callable[[Any], str]           # trusted, fast
    brute: Callable[[Any], str]           # trusted, obviously correct, slow
    features: Callable[[Any], list]       # edge-features of a case, e.g. "all_negative"
    size: Callable[[Any], int]
    hints: tuple[str, str, str, str]      # level 1..4; level 4 is structure only, no code
    rubric: str                           # what a viable first step looks like
    spoilers: dict                        # term -> minimum hint level at which it may appear
    reference_src: str                    # python reference, used by leak check (5-gram overlap)
    tier: str = "free"                    # "free" or "pro" (paid pack, locked until a code is redeemed)

    def public(self) -> dict:
        return {
            "id": self.id, "title": self.title, "difficulty": self.difficulty, "tags": list(self.tags),
            "statement": self.statement, "input_format": self.input_format,
            "output_format": self.output_format, "constraints": self.constraints, "tier": self.tier,
            "samples": [{"input": i, "output": o} for i, o in self.samples],
        }


def list_shrinks(xs: list, min_len: int = 1) -> list[list]:
    """Candidate simpler lists: drop a chunk, drop one element, move values toward 0."""
    out: list[list] = []
    n = len(xs)
    if n > min_len:
        half = n // 2
        if half >= min_len:
            out.append(xs[:half])
            out.append(xs[n - half:])
        for i in range(n):
            out.append(xs[:i] + xs[i + 1:])
    for i, v in enumerate(xs):
        if v != 0:
            for nv in (0, v // 2, v - (1 if v > 0 else -1)):
                if abs(nv) < abs(v):
                    out.append(xs[:i] + [nv] + xs[i + 1:])
    return out


def fmt_list(xs: list) -> str:
    return f"{len(xs)}\n{' '.join(map(str, xs))}\n"
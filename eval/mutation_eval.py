"""Mutation evaluation of the counterexample finder.

Wrong programs are made by mutating the correct reference solutions (AST operator/constant changes).
Ground truth ("is this mutant really wrong?") comes from the oracle on 1500 held-out random tests
(seed 999). We keep only mutants that PASS the public samples - the ones a learner would believe are
right - and ask which test-generation strategy finds a failing input within the same budget.

Honest limits: mutants are synthetic, not real student bugs; ground truth uses small inputs (sizes <= 8),
so a mutant that fails only on big inputs counts as correct here. Real submissions: see docs/EVAL_RESULTS.md.
Uses an in-process executor for speed; the sandboxed runner is covered by tests.
"""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import random
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.counterexample import find_counterexample  # noqa: E402
from app.problems import PROBLEMS  # noqa: E402
from app.runner import OK, RE, TLE, RunResult, same_output  # noqa: E402
from eval.solutions import SOLUTIONS  # noqa: E402


class FastProgram:
    verdict = OK
    detail = ""

    def __init__(self, code: str):
        self.code = compile(code, "<mutant>", "exec")

    def run(self, stdin: str) -> RunResult:
        def on_alarm(*_):
            raise TimeoutError

        old = signal.signal(signal.SIGALRM, on_alarm)
        buf, old_in = io.StringIO(), sys.stdin
        sys.stdin = io.StringIO(stdin)
        signal.setitimer(signal.ITIMER_REAL, 0.3)
        try:
            with contextlib.redirect_stdout(buf):
                exec(self.code, {"__name__": "__main__"})
            return RunResult(OK, buf.getvalue())
        except TimeoutError:
            return RunResult(TLE, "", "timeout")
        except BaseException as e:  # noqa: BLE001
            return RunResult(RE, buf.getvalue(), type(e).__name__)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
            sys.stdin = old_in


# ---------------------------------------------------------------- mutation operators
SWAP_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Add}
SWAP_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq}


def mutants(src: str) -> list[str]:
    tree = ast.parse(src)
    nodes = [n for n in ast.walk(tree)]
    out: dict[str, None] = {}
    for idx, node in enumerate(nodes):
        variants = []
        if isinstance(node, ast.BinOp) and type(node.op) in SWAP_BIN:
            variants.append(("op", SWAP_BIN[type(node.op)]()))
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in SWAP_CMP:
            variants.append(("cmp", SWAP_CMP[type(node.ops[0])]()))
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            for d in (1, -1):
                variants.append(("const", node.value + d))
        if isinstance(node, ast.Name) and node.id in ("max", "min"):
            variants.append(("name", "min" if node.id == "max" else "max"))
        for kind, v in variants:
            t = copy.deepcopy(tree)
            n = [x for x in ast.walk(t)][idx]
            if kind == "op":
                n.op = v
            elif kind == "cmp":
                n.ops = [v]
            elif kind == "const":
                n.value = v
            else:
                n.id = v
            try:
                text = ast.unparse(ast.fix_missing_locations(t))
            except Exception:
                continue
            out[text] = None
    # statement deletion (inside bodies that keep at least one statement)
    for idx, node in enumerate(nodes):
        for field in ("body", "orelse"):
            body = getattr(node, field, None)
            if isinstance(body, list) and len(body) > 1:
                for j in range(len(body)):
                    t = copy.deepcopy(tree)
                    n = [x for x in ast.walk(t)][idx]
                    del getattr(n, field)[j]
                    try:
                        out[ast.unparse(ast.fix_missing_locations(t))] = None
                    except Exception:
                        pass
    # variable swap: replace one loaded name by another name defined in the program
    names = sorted({n.id for n in nodes if isinstance(n, ast.Name) and n.id not in
                    ("max", "min", "int", "map", "list", "input", "print", "range", "set", "sorted", "str")})
    for idx, node in enumerate(nodes):
        if isinstance(node, ast.Name) and node.id in names and isinstance(node.ctx, ast.Load):
            for other in names:
                if other != node.id:
                    t = copy.deepcopy(tree)
                    [x for x in ast.walk(t)][idx].id = other
                    try:
                        out[ast.unparse(ast.fix_missing_locations(t))] = None
                    except Exception:
                        pass
    out.pop(ast.unparse(tree), None)
    return list(out)


def wrong_on(p, prog, cases) -> bool:
    for c in cases:
        r = prog.run(p.fmt(c))
        if r.verdict != OK or not same_output(p.solve(c), r.stdout):
            return True
    return False


def main() -> str:
    rows, t0 = [], time.time()
    shrink_before, shrink_after = [], []
    for pid, p in PROBLEMS.items():
        gt_rng = random.Random(999)
        truth_cases = p.edge_cases() + [p.gen(gt_rng, i) for i in range(1500)]
        r7 = random.Random(7)
        rand150 = [p.gen(r7, i) for i in range(150)]
        rand30 = rand150[:30]
        n_all = n_wrong = n_sample_ok = 0
        hit30 = hit150 = hit_find = 0
        for m in mutants(SOLUTIONS[pid]):
            n_all += 1
            try:
                prog = FastProgram(m)
            except SyntaxError:
                continue
            if not wrong_on(p, prog, truth_cases):
                continue  # equivalent (or only wrong on inputs we did not generate): discard
            n_wrong += 1
            samples_ok = all(same_output(o, prog.run(i).stdout) and prog.run(i).verdict == OK for i, o in p.samples)
            if not samples_ok:
                continue
            n_sample_ok += 1
            hit30 += wrong_on(p, prog, rand30)
            hit150 += wrong_on(p, prog, rand150)
            res = find_counterexample(p, "python", "", program=prog)
            if res["status"] == "found":
                hit_find += 1
                shrink_before.append(res["size_before"])
                shrink_after.append(res["size_after"])
        rows.append((pid, n_all, n_wrong, n_sample_ok, hit30, hit150, hit_find))
    secs = time.time() - t0
    tot = [sum(r[i] for r in rows) for i in range(1, 7)]
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "n/a"  # noqa: E731
    md = ["# Evaluation: does the finder expose bugs that pass the samples?", "",
          "Synthetic mutants of correct reference solutions (not real student bugs). Ground truth: oracle on 1500 "
          "held-out random tests plus edge cases (seed 999); finder and baselines use seed 7, 150-test budget.",
          "Only mutants that are really wrong AND pass every public sample are scored (those are the ones a learner "
          "would trust).", "",
          "| problem | mutants | really wrong | wrong but pass samples | random x30 | random x150 | finder (edge + random x150) |",
          "|---|---|---|---|---|---|---|"]
    for pid, a, w, s, h30, h150, hf in rows:
        md.append(f"| {pid} | {a} | {w} | {s} | {pct(h30, s)} | {pct(h150, s)} | {pct(hf, s)} |")
    md.append(f"| **all** | {tot[0]} | {tot[1]} | {tot[2]} | **{pct(tot[3], tot[2])}** | **{pct(tot[4], tot[2])}** | "
              f"**{pct(tot[5], tot[2])}** |")
    if shrink_before:
        md += ["", f"Shrinking: mean failing-input size {sum(shrink_before) / len(shrink_before):.1f} before, "
                   f"{sum(shrink_after) / len(shrink_after):.1f} after (n={len(shrink_before)})."]
    from eval.pitfalls import PITFALLS
    ph = [0, 0, 0]
    pit_rows = []
    for pid, name, code, _ in PITFALLS:
        p = PROBLEMS[pid]
        prog = FastProgram(code)
        ph[0] += wrong_on(p, prog, [p.gen(random.Random(7), i) for i in range(30)] if False else
                          [c for r7 in [random.Random(7)] for c in [p.gen(r7, i) for i in range(30)]])
        r7 = random.Random(7)
        ph[1] += wrong_on(p, prog, [p.gen(r7, i) for i in range(150)])
        res = find_counterexample(p, "python", "", program=prog)
        ph[2] += res["status"] == "found"
        pit_rows.append(f"| {pid} | {name} | {res['status']} | {res.get('size_before')} -> {res.get('size_after')} | "
                        f"{', '.join(res.get('features', [])) or '-'} |")
    md += ["", f"## Hand-written classic pitfalls ({len(PITFALLS)} wrong programs that pass the samples)", "",
           f"Random x30 finds {ph[0]}/{len(PITFALLS)}, random x150 finds {ph[1]}/{len(PITFALLS)}, "
           f"finder finds {ph[2]}/{len(PITFALLS)}.", "",
           "| problem | bug | status | input size before -> after shrinking | failure features |", "|---|---|---|---|---|"] + pit_rows
    md += ["", "Samples alone find 0% of these by construction (they pass the samples).", "",
           f"Run time {secs:.0f}s. Reproduce: `python -m eval.mutation_eval`.", "",
           "## Limits", "- Mutants are not real student mistakes. Run the dataset evaluation (below) for that.",
           "- Ground truth only covers small inputs; mutants wrong only on large inputs are discarded as equivalent.",
           "- Edge cases were written by the same author as the problems, so the edge-seeding arm is partly tuned "
           "to these problems. A held-out set of real wrong submissions is the honest test."]
    return "\n".join(md) + "\n"


if __name__ == "__main__":
    text = main()
    out = Path(__file__).resolve().parent.parent / "docs" / "EVAL_RESULTS.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text)
    print(text)
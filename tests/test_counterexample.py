import pytest
from app.problems import PROBLEMS
from app.counterexample import find_counterexample
from app.runner import Program

BUGGY_MAXSUB = """n=int(input());a=list(map(int,input().split()))
best=0;cur=0
for x in a:
    cur=max(0,cur+x);best=max(best,cur)
print(best)
"""
GOOD_MAXSUB = """n=int(input());a=list(map(int,input().split()))
best=cur=a[0]
for x in a[1:]:
    cur=max(x,cur+x);best=max(best,cur)
print(best)
"""
BUGGY_PAIRS = """n,k=map(int,input().split());a=list(map(int,input().split()))
print(sum(1 for x in a for y in a if x+y==k)//2)
"""
LOOP_FOREVER = "while True: pass\n"
BAD_IMPORT = "import os\nos.system('echo hi')\n"
CPP_BUGGY = r"""#include <bits/stdc++.h>
using namespace std;
int main(){int n;cin>>n;vector<long long>a(n);for(auto&x:a)cin>>x;long long best=0,cur=0;
for(auto x:a){cur=max(0LL,cur+x);best=max(best,cur);}cout<<best<<endl;}
"""


def test_buggy_found_and_minimal():
    r = find_counterexample(PROBLEMS["max-subarray"], "python", BUGGY_MAXSUB)
    assert r["status"] == "found"
    assert "all_negative" in r["features"]
    assert r["size_after"] == 1 and r["input"].split()[-1].startswith("-")
    assert r["expected"] != r["got"]


def test_correct_not_flagged():
    r = find_counterexample(PROBLEMS["max-subarray"], "python", GOOD_MAXSUB)
    assert r["status"] == "none_found"


def test_pairs_self_pair_trap():
    r = find_counterexample(PROBLEMS["count-pairs-sum"], "python", BUGGY_PAIRS)
    assert r["status"] == "found"
    assert "self_pair_trap" in r["features"]


def test_tle_reported():
    r = find_counterexample(PROBLEMS["max-subarray"], "python", LOOP_FOREVER, timeout=0.5)
    assert r["status"] == "fails_sample" and r["verdict"] == "TLE"


def test_banned_import_rejected():
    r = find_counterexample(PROBLEMS["max-subarray"], "python", BAD_IMPORT)
    assert r["status"] == "cannot_run" and r["verdict"] == "REJECTED"


def test_syntax_error_is_ce():
    r = find_counterexample(PROBLEMS["max-subarray"], "python", "print(")
    assert r["status"] == "cannot_run" and r["verdict"] == "CE"


def test_cpp_buggy_found():
    r = find_counterexample(PROBLEMS["max-subarray"], "cpp", CPP_BUGGY)
    assert r["status"] == "found" and "all_negative" in r["features"]


@pytest.mark.parametrize("pid", list(PROBLEMS))
def test_correct_reference_program_passes_samples_and_finder(pid):
    from eval.solutions import SOLUTIONS
    r = find_counterexample(PROBLEMS[pid], "python", SOLUTIONS[pid])
    assert r["status"] == "none_found", r


def test_classic_pitfalls_are_found():
    from eval.pitfalls import PITFALLS
    miss = []
    for pid, name, code, feat in PITFALLS:
        r = find_counterexample(PROBLEMS[pid], "python", code)
        if r["status"] != "found" or (feat and feat not in r["features"]):
            miss.append((pid, name, r["status"], r.get("features")))
    assert not miss, miss
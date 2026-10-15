"""Correct stdin->stdout Python programs, one per problem. Used by tests and the mutation evaluation."""
SOLUTIONS = {
"max-subarray": """n = int(input())
a = list(map(int, input().split()))
best = cur = a[0]
for x in a[1:]:
    cur = max(x, cur + x)
    best = max(best, cur)
print(best)
""",
"count-pairs-sum": """n, k = map(int, input().split())
a = list(map(int, input().split()))
seen = {}
total = 0
for x in a:
    total += seen.get(k - x, 0)
    seen[x] = seen.get(x, 0) + 1
print(total)
""",
"longest-equal-run": """n = int(input())
a = list(map(int, input().split()))
best = run = 1
for i in range(1, n):
    if a[i] == a[i - 1]:
        run += 1
    else:
        run = 1
    best = max(best, run)
print(best)
""",
"balanced-brackets": """s = input().strip()
pairs = {')': '(', ']': '[', '}': '{'}
st = []
ok = True
for ch in s:
    if ch in '([{':
        st.append(ch)
    else:
        if not st or st.pop() != pairs[ch]:
            ok = False
            break
print('YES' if ok and not st else 'NO')
""",
"range-sum-queries": """n, q = map(int, input().split())
a = list(map(int, input().split()))
pre = [0]
for x in a:
    pre.append(pre[-1] + x)
for _ in range(q):
    l, r = map(int, input().split())
    print(pre[r] - pre[l - 1])
""",
"second-largest-distinct": """n = int(input())
a = list(map(int, input().split()))
d = sorted(set(a))
print(d[-2] if len(d) >= 2 else 'NONE')
""",
"longest-fresh-stretch": """n = int(input())
a = list(map(int, input().split()))
last = {}
left = best = 0
for i, x in enumerate(a):
    if x in last:
        left = max(left, last[x] + 1)
    last[x] = i
    best = max(best, i - left + 1)
print(best)
""",
"exact-target-blocks": """n, k = map(int, input().split())
a = list(map(int, input().split()))
seen = {0: 1}
s = t = 0
for x in a:
    s += x
    t += seen.get(s - k, 0)
    seen[s] = seen.get(s, 0) + 1
print(t)
""",
}

"""Hand-written beginner bugs that PASS the public samples (the classic pitfalls). (problem, name, code, expected feature)"""
PITFALLS = [
("max-subarray", "init best=0", "n=int(input());a=list(map(int,input().split()))\nb=c=0\nfor x in a:\n    c=max(0,c+x);b=max(b,c)\nprint(b)\n", "all_negative"),
("max-subarray", "brute skips singles", "n=int(input());a=list(map(int,input().split()))\nb=-10**18\nfor i in range(n):\n    for j in range(i+1,n):\n        b=max(b,sum(a[i:j+1]))\nprint(b if n>1 else 0)\n", "single_element"),
("count-pairs-sum", "double loop counts i==j", "n,k=map(int,input().split());a=list(map(int,input().split()))\nt=0\nfor i in range(n):\n    for j in range(i,n):\n        t+=a[i]+a[j]==k\nprint(t)\n", "self_pair_trap"),
("count-pairs-sum", "set ignores duplicates", "n,k=map(int,input().split());a=list(map(int,input().split()))\ns=set(a)\nprint(sum(1 for x in s if k-x in s and x<k-x))\n", "duplicates"),
("longest-equal-run", "no update after loop", "n=int(input());a=list(map(int,input().split()))\nb=0;r=1\nfor i in range(1,n):\n    if a[i]==a[i-1]:\n        r+=1\n    else:\n        b=max(b,r);r=1\nprint(b)\n", "single_element"),
("longest-equal-run", "counts equal values anywhere", "n=int(input());a=list(map(int,input().split()))\nprint(max(a.count(x) for x in a))\n", None),
("balanced-brackets", "pops empty / no empty check", "s=input().strip()\np={')':'(',']':'[','}':'{'}\nst=[]\nfor ch in s:\n    if ch in '([{':\n        st.append(ch)\n    elif st and st[-1]==p[ch]:\n        st.pop()\nprint('YES' if not st else 'NO')\n", None),
("balanced-brackets", "counts only", "s=input().strip()\nprint('YES' if s.count('(')==s.count(')') and s.count('[')==s.count(']') and s.count('{')==s.count('}') else 'NO')\n", None),
("range-sum-queries", "prefix without leading 0 (l=1 wraps)", "n,q=map(int,input().split());a=list(map(int,input().split()))\npre=[]\ns=0\nfor x in a:\n    s+=x;pre.append(s)\nfor _ in range(q):\n    l,r=map(int,input().split())\n    print(pre[r-1]-pre[l-2])\n", "query_starts_at_1"),
("range-sum-queries", "single-position query returns 0", "n,q=map(int,input().split());a=list(map(int,input().split()))\nfor _ in range(q):\n    l,r=map(int,input().split())\n    print(sum(a[l-1:r]) if l<r else 0)\n", "single_element_query"),
("second-largest-distinct", "sorted[-2] keeps duplicates", "n=int(input());a=sorted(map(int,input().split()))\nprint(a[-2] if n>1 else 'NONE')\n", "max_repeated"),
("second-largest-distinct", "init second=0", "n=int(input());a=list(map(int,input().split()))\nm=max(a);s=0\nfor x in a:\n    if x<m: s=max(s,x)\nprint(s if s else 'NONE')\n", None),
]
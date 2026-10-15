from app.runner import Program


def run(code, stdin="1 2 3\n"):
    with Program.prepare("python", code) as p:
        return p.verdict, (p.run(stdin).stdout.strip() if p.verdict == "OK" else p.detail)


def test_indented_paste_runs():
    assert run("     import sys\n     d = sys.stdin.read().split()\n     for x in d:\n         pass\n     print(len(d))\n") == ("OK", "3")


def test_windows_line_endings_and_bom():
    assert run("\ufeffprint(1)\r\nprint(2)\r\n") == ("OK", "1\n2")


def test_genuinely_bad_indent_is_still_an_error():
    verdict, _ = run("print(1)\n    print(2)\n")
    assert verdict == "CE"

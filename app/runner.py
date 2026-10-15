"""Run learner code against stdin with limits.

HONEST NOTE: this is best-effort isolation (AST/regex denylist, rlimits, timeout, process-group kill,
temp dir, `python3 -I`). It is NOT a security boundary. A public deployment must run each job in a
container/sandbox with no network and a read-only filesystem. The Dockerfile runs as a non-root user.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass

OK, RE, TLE, CE, REJECTED = "OK", "RE", "TLE", "CE", "REJECTED"

_PY_BANNED_MODULES = {"os", "subprocess", "socket", "shutil", "ctypes", "multiprocessing", "urllib",
                      "http", "requests", "pathlib", "importlib", "sys_exit_hack", "signal", "threading",
                      "io", "builtins", "gc", "inspect", "marshal", "pickle", "code", "codeop", "pty", "resource",
                      "fcntl", "posix", "nt", "_thread", "asyncio", "concurrent", "select", "selectors", "mmap",
                      "tempfile", "glob", "types", "runpy", "site", "ssl", "ftplib", "smtplib", "webbrowser"}
_PY_BANNED_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input_hook", "getattr", "setattr",
                    "delattr", "globals", "locals", "vars", "memoryview"}
_PY_BANNED_ATTRS = {"modules", "builtins", "f_globals", "f_locals", "f_back", "gi_frame", "tb_frame"}
_CPP_BANNED = re.compile(r"\b(system|popen|fork|execv?[a-z]*|fopen|ifstream|ofstream|socket|asm|__asm__|open|openat|"
                         r"syscall|dlopen|ptrace|mmap|thread|pthread_\w+|async|filesystem|getenv|environ)\b")
_CPP_BAD_INCLUDE = re.compile(r"<\s*(unistd|fcntl|dlfcn|signal|csignal|pthread|thread|future|filesystem|"
                              r"sys/[\w./]+|linux/[\w./]+)(\.h)?\s*>")
_CPP_INCLUDE = re.compile(r'^\s*#\s*include\s*(.*)$', re.M)
MAX_OUT = 1_000_000


@dataclass
class RunResult:
    verdict: str
    stdout: str = ""
    detail: str = ""


def _py_check(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"CE:{e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in _PY_BANNED_MODULES:
                    return f"REJ:import {a.name} is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in _PY_BANNED_MODULES:
                return f"REJ:import {node.module} is not allowed"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _PY_BANNED_CALLS:
                return f"REJ:{node.func.id}() is not allowed"
            if node.func.id == "open":
                a0 = node.args[0] if node.args else None
                if not (isinstance(a0, ast.Constant) and a0.value == 0):
                    return "REJ:open() is not allowed (only open(0) for stdin)"
        elif isinstance(node, ast.Name) and node.id in {"__builtins__", "__loader__", "__spec__"}:
            return f"REJ:{node.id} is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr in _PY_BANNED_ATTRS:
            return f"REJ:attribute {node.attr} is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            if node.attr not in {"__name__", "__len__", "__init__", "__str__", "__repr__", "__eq__", "__lt__"}:
                return f"REJ:attribute {node.attr} is not allowed"
    return None


def _cpp_check(code: str) -> str | None:
    for m in _CPP_INCLUDE.finditer(code):
        if not m.group(1).strip().startswith("<"):
            return "REJ:only <standard> includes are allowed"
        if _CPP_BAD_INCLUDE.match(m.group(1).strip()):
            return "REJ:that include is not allowed"
    if _CPP_BANNED.search(code):
        return "REJ:a banned call was found"
    return None


def _limits(timeout: float):
    def apply():
        try:
            import resource
            mb = 512 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mb, mb))
            c = int(timeout) + 2
            resource.setrlimit(resource.RLIMIT_CPU, (c, c))
            resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))  # learner code cannot start processes/threads
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except Exception:
            pass
        os.setsid()
    return apply


def _child_env() -> dict:
    """Minimal environment for learner programs (no secrets). Windows needs SystemRoot to start at all."""
    if os.name == "nt":
        return {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "PATH", "TEMP", "TMP")}
    return {"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0"}


class Program:
    """Prepared learner program. Create with Program.prepare(); call .run(stdin); call .close()."""

    def __init__(self, language: str, workdir: str | None, cmd: list[str] | None, verdict: str, detail: str,
                 timeout: float):
        self.language, self.workdir, self.cmd = language, workdir, cmd
        self.verdict, self.detail, self.timeout = verdict, detail, timeout

    @classmethod
    def prepare(cls, language: str, code: str, timeout: float = 2.0) -> "Program":
        language = language.lower()
        code = textwrap.dedent(code.replace("\r\n", "\n").lstrip("\ufeff")).strip("\n") + "\n"  # pasted code is often indented
        if len(code) > 20_000:
            return cls(language, None, None, REJECTED, "code is too long", timeout)
        if language in ("python", "py", "python3"):
            bad = _py_check(code)
            if bad:
                kind, _, msg = bad.partition(":")
                return cls("python", None, None, CE if kind == "CE" else REJECTED, msg, timeout)
            d = tempfile.mkdtemp(prefix="fs_")
            path = os.path.join(d, "sol.py")
            with open(path, "w") as f:
                f.write(code)
            return cls("python", d, [sys.executable, "-I", path], OK, "", timeout)
        if language in ("cpp", "c++"):
            bad = _cpp_check(code)
            if bad:
                return cls("cpp", None, None, REJECTED, bad.partition(":")[2], timeout)
            if not shutil.which("g++"):
                return cls("cpp", None, None, REJECTED, "g++ is not available on this server", timeout)
            d = tempfile.mkdtemp(prefix="fs_")
            src, exe = os.path.join(d, "sol.cpp"), os.path.join(d, "sol.exe" if os.name == "nt" else "sol")
            with open(src, "w") as f:
                f.write(code)
            try:
                p = subprocess.run(["g++", "-O2", "-std=c++17", src, "-o", exe], capture_output=True,
                                   text=True, timeout=15)
            except subprocess.TimeoutExpired:
                shutil.rmtree(d, ignore_errors=True)
                return cls("cpp", None, None, CE, "compile timed out", timeout)
            if p.returncode != 0:
                shutil.rmtree(d, ignore_errors=True)
                return cls("cpp", None, None, CE, p.stderr[-600:], timeout)
            return cls("cpp", d, [exe], OK, "", timeout)
        return cls(language, None, None, REJECTED, f"unsupported language {language!r}", timeout)

    def run(self, stdin: str) -> RunResult:
        if self.verdict != OK or not self.cmd or not self.workdir:
            return RunResult(self.verdict, "", self.detail)
        in_path = os.path.join(self.workdir, "in.txt")
        out_path = os.path.join(self.workdir, "out.txt")
        with open(in_path, "w") as fi:
            fi.write(stdin)
        try:
            with open(in_path) as fi, open(out_path, "w") as fo:
                proc = subprocess.Popen(self.cmd, stdin=fi, stdout=fo, stderr=subprocess.PIPE, cwd=self.workdir,
                                        preexec_fn=_limits(self.timeout) if os.name == "posix" else None,
                                        env=_child_env())
                try:
                    _, err = proc.communicate(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    self._kill(proc)
                    return RunResult(TLE, "", f"no answer within {self.timeout:g}s")
        except OSError as e:
            return RunResult(RE, "", str(e))
        with open(out_path, errors="replace") as fo:
            out = fo.read(MAX_OUT)
        if proc.returncode != 0:
            tail = (err or b"").decode(errors="replace").strip().splitlines()[-1:] or [""]
            return RunResult(RE, out, tail[0][:200])
        return RunResult(OK, out)

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass

    def close(self) -> None:
        if self.workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def same_output(expected: str, got: str) -> bool:
    """Token-wise comparison (whitespace-insensitive), like most judges."""
    return expected.split() == got.split()
from .base import Problem
from .bank import PROBLEMS as _FREE
from .pro_pack import PRO_PROBLEMS

PROBLEMS = {**_FREE, **PRO_PROBLEMS}


def get(pid: str) -> Problem:
    return PROBLEMS[pid]

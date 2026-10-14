from .base import Problem
from .bank import PROBLEMS


def get(pid: str) -> Problem:
    return PROBLEMS[pid]
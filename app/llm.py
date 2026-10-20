"""Pluggable open-model adapter. Jobs are narrow on purpose: classify a first step, rephrase a hint,
explain a counterexample in words. The model never grades code and never writes solutions; code does
that (counterexample finder, leak check). If no model is configured every job returns None and the
deterministic fallbacks are used, so the app works with LLM_PROVIDER=none."""
from __future__ import annotations

import os

import httpx

from . import observability

from .config import Settings

SYS = ("You are a patient tutor for a beginner learning competitive programming. Never write code. "
       "Never state the final algorithm or the answer. Reply in plain English, at most 3 short sentences.")


class ChatClient:
    name = "base"
    model = ""
    job = "chat"

    def chat(self, job: str, system: str, user: str) -> str:
        """All model calls go through here so each one is traced (job, model; never the text)."""
        with observability.llm_span(job, self.name, self.model or self.name):
            return self._chat(system, user)

    def _chat(self, system: str, user: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def judge_first_step(self, statement: str, text: str) -> str | None:
        out = self.chat("judge_first_step",
            "Classify the learner's first step. Answer with exactly one word from: restate, small_example, "
            "brute_force, observation, too_vague.",
            f"Problem:\n{statement}\n\nLearner's first step:\n{text}")
        word = out.strip().lower().split()[0].strip(".,:;\"'") if out.strip() else ""
        return word or None

    def rephrase_hint(self, statement: str, hint: str, level: int) -> str | None:
        return self.chat("rephrase_hint", SYS, f"Problem:\n{statement}\n\nRewrite this hint in friendlier words. Keep its meaning "
                               f"and do not add new information:\n{hint}").strip() or None

    def explain_counterexample(self, statement: str, inp: str, expected: str, got: str) -> str | None:
        return self.chat("explain_counterexample", SYS, f"Problem:\n{statement}\n\nA learner's program was run on this input:\n{inp}\n"
                               f"Expected output: {expected}\nTheir output: {got}\n"
                               "Explain, without code and without giving the fix, what kind of situation "
                               "this input tests and what to re-read in their own logic.").strip() or None


class OllamaClient(ChatClient):
    name = "ollama"

    def __init__(self, url: str, model: str):
        self.url, self.model = url.rstrip("/"), model

    def _chat(self, system: str, user: str) -> str:
        r = httpx.post(f"{self.url}/api/chat", timeout=60, json={
            "model": self.model, "stream": False, "think": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0.2}})
        r.raise_for_status()
        return r.json()["message"]["content"]


class OpenAICompatClient(ChatClient):
    """Any OpenAI-compatible endpoint, e.g. DigitalOcean serverless inference hosting an open model."""
    name = "openai"

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base, self.key, self.model = base_url.rstrip("/"), api_key, model

    def _chat(self, system: str, user: str) -> str:
        r = httpx.post(f"{self.base}/chat/completions", timeout=60,
                       headers={"Authorization": f"Bearer {self.key}"},
                       json={"model": self.model, "temperature": 0.2, "max_tokens": 250,
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ---- Tinker: the fine-tuned first-step classifier --------------------------------------------------------
TINKER_BASE_URL = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
TINKER_LABELS = ("restate", "small_example", "brute_force", "observation", "too_vague")


def tinker_prompt(statement: str, text: str) -> str:
    """MUST stay byte-identical to prompt() in tinker_ft/train_firststep.py. The model was fine-tuned on this
    raw text format, not on a chat template, so it is queried through /completions, never /chat/completions."""
    return (f"Problem: {statement}\n"
            f"Learner's first step: {text}\n"
            f"Classify as one of {', '.join(TINKER_LABELS)}.\n"
            f"Label:")


class TinkerClient(ChatClient):
    """The LoRA-tuned Qwen3-8B sampler checkpoint, served by Tinker's OpenAI-compatible endpoint.
    It is a classifier, so it does exactly one job. Hint rewording and counterexample explanations return None,
    which makes the app use its static, leak-checked text instead."""
    name = "tinker"
    model_label = "qwen3-8b-firststep-lora"

    def __init__(self, api_key: str, model: str, base_url: str = TINKER_BASE_URL, timeout: float = 8.0):
        self.key, self.model, self.base, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    def judge_first_step(self, statement: str, text: str) -> str | None:
        with observability.llm_span("judge_first_step", self.name, self.model_label):
            r = httpx.post(f"{self.base}/completions", timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.key}"},
                           json={"model": self.model, "prompt": tinker_prompt(statement, text),
                                 "max_tokens": 6, "temperature": 0})
            r.raise_for_status()
            out = (r.json()["choices"][0].get("text") or "").strip()
        word = out.split()[0].strip(".,:;\"'").lower() if out else ""
        return word or None

    def rephrase_hint(self, statement: str, hint: str, level: int) -> str | None:
        return None

    def explain_counterexample(self, statement: str, inp: str, expected: str, got: str) -> str | None:
        return None


class FakeClient(ChatClient):
    """For tests: canned replies."""
    name = "fake"

    def __init__(self, reply: str = "Think about the smallest input where your logic might break."):
        self.reply = reply

    def _chat(self, system: str, user: str) -> str:
        return self.reply


def get_client(s: Settings) -> ChatClient | None:
    if s.llm_provider == "ollama":
        return OllamaClient(s.ollama_url, s.ollama_model)
    if s.llm_provider == "openai" and s.llm_base_url and s.llm_model:
        return OpenAICompatClient(s.llm_base_url, s.llm_api_key, s.llm_model)
    if s.llm_provider == "tinker" and s.llm_model:
        key = s.llm_api_key or os.environ.get("TINKER_API_KEY", "")
        if key:
            return TinkerClient(key, s.llm_model, s.llm_base_url or TINKER_BASE_URL, s.llm_timeout_s)
    return None
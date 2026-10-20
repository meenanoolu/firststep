import httpx
from app.config import Settings
from app.llm import TinkerClient, TINKER_BASE_URL, get_client, tinker_prompt
from app import firststep
import dataclasses


class Resp:
    def __init__(self, text, status=200):
        self._t, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return {"choices": [{"text": self._t}]}


def test_prompt_matches_training_format():
    p = tinker_prompt("S", "T")
    assert p == ("Problem: S\nLearner's first step: T\n"
                 "Classify as one of restate, small_example, brute_force, observation, too_vague.\nLabel:")


def test_uses_completions_endpoint_and_parses_label(monkeypatch):
    seen = {}

    def fake_post(url, **kw):
        seen["url"], seen["json"], seen["headers"] = url, kw["json"], kw["headers"]
        return Resp(" small_example\n")
    monkeypatch.setattr(httpx, "post", fake_post)
    c = TinkerClient("KEY", "tinker://run:train:0/sampler_weights/x")
    assert c.judge_first_step("S", "T") == "small_example"
    assert seen["url"] == TINKER_BASE_URL + "/completions"
    assert seen["json"]["model"].startswith("tinker://") and seen["json"]["temperature"] == 0
    assert seen["headers"]["Authorization"] == "Bearer KEY"


def test_prose_jobs_are_not_sent_to_the_classifier(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call expected")))
    c = TinkerClient("K", "tinker://x")
    assert c.rephrase_hint("S", "h", 1) is None and c.explain_counterexample("S", "1", "2", "3") is None


def test_outage_falls_back_to_rules(monkeypatch):
    def down(*a, **k):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(httpx, "post", down)
    res = firststep.judge("Given n integers, find the best sum.",
                          "I would try all blocks with two loops and keep the best", TinkerClient("K", "tinker://x"))
    assert res["source"] == "rules" and res["viable"]


def test_garbage_label_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: Resp("Sure! Here is"))
    res = firststep.judge("Given n integers, find the best sum.",
                          "I would try all blocks with two loops and keep the best", TinkerClient("K", "tinker://x"))
    assert res["source"] == "rules"


def test_get_client_wiring(monkeypatch):
    monkeypatch.delenv("TINKER_API_KEY", raising=False)
    s = dataclasses.replace(Settings(), llm_provider="tinker", llm_model="tinker://x", llm_api_key="K", llm_base_url="")
    c = get_client(s)
    assert isinstance(c, TinkerClient) and c.base == TINKER_BASE_URL
    assert get_client(dataclasses.replace(s, llm_api_key="")) is None   # no key: stay on rules
# FirstStep

A practice tool for people who keep solving the same coding problems by memory and then freeze on anything new.

**Live demo:** https://hacktoberfeste6c4p8.tech  
**Also on Render:** https://firststep-jtuf.onrender.com  
**Repo:** https://github.com/meenanoolu/firststep

Before you write any code you must state one concrete first move.  
If your code is wrong, the tool returns a **tiny input you can trace by hand** that breaks it, plus a short plain-language reason.  
It does not dump a full solution.

---

## Why this exists

Many beginners (and some of us who already know the patterns) pass samples by recognition, then blank when the same idea appears in a slightly different shape.

FirstStep forces the starting move and shows the smallest counterexample instead of a green checkmark or a full answer. The goal is a habit: start with something concrete, then debug against a hand-traceable input.

---

## What it does

1. **First-step gate**  
   You write one sentence about how you would begin (tiny example, try-everything loop, or one thing you would track).  
   Vague restatements are rejected. A small open-weight model can classify the sentence; if the model is off or uncertain, deterministic rules take over.

2. **Sandboxed run**  
   Your Python is executed with resource limits and a short timeout. Only the allowed problem surface is available.

3. **Minimal failing input**  
   A brute-force oracle + shrinker looks for the smallest input that makes your program disagree with the correct answer. The finder is budgeted so a slow or broken program cannot hang the server.

4. **Failure profile**  
   Each wrong submission is tagged (`all_negative`, `single_element`, `self_pair_trap`, …). Over a session you see which shapes keep beating you.

5. **Leak-checked hints**  
   Hints and model explanations are filtered so they do not hand you the full solution.

6. **Session report + spaced reviews**  
   When you finish a problem you get a short report of the failure shapes you hit. Review intervals are stored per learner.

7. **Optional paid unlock**  
   A “full learning report” and a small extra problem pack can be unlocked with a license code (hand-issued or Gumroad). Free tier stays usable forever.

---

## Open-model usage

The tutor path is optional.

| Setting | Behaviour |
|---------|-----------|
| `LLM_PROVIDER=none` (default) | Rules + deterministic explanations only. No external calls. |
| `LLM_PROVIDER=ollama` | Local Gemma (or any model you pull) via Ollama for first-step classification, hint rephrasing, and counterexample explanation. |
| `LLM_PROVIDER=openai` | Any OpenAI-compatible endpoint (hosted open models). |

When the model is used, every reply is leak-checked. If the model fails or is unreachable the tool still works.

Local example (already tested with Gemma):

```bash
ollama pull gemma2:2b          # or whatever tag you prefer
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=gemma2:2b
uvicorn app.main:app --reload
```

On Render the service runs with `LLM_PROVIDER=none` so demos stay fast and free. Point a local Ollama instance at the same code when you want the model path.

---

## Fine-tuning with Tinker (optional upgrade)

The first-step classifier can be improved with a small LoRA fine-tune. Script and data:

- `tinker_ft/train_firststep.py` — trains + evaluates
- `data/firststep_train.jsonl` — 60 labelled examples
- `data/firststep_test.jsonl` — 20 held-out examples

**Results on the held-out set:**

| Method | Accuracy | Viable accuracy | Latency (sec/call) |
|--------|----------|-----------------|--------------------|
| Base model (before fine-tune) | 0.20 | 0.45 | 7.22 |
| **Tuned model (after Tinker LoRA)** | **0.55** | **0.80** | 7.11 |

To re-run (needs a Tinker API key and credit):

```bash
pip install tinker
# Windows PowerShell:
$env:TINKER_API_KEY = "your_key"
python -m tinker_ft.train_firststep
```

Production still defaults to the deterministic rules so the product never depends on the fine-tuned model.

---

## Problems included

Six free beginner problems (max-subarray style “Best stretch”, pair sum, brackets, longest run, range queries, etc.).  
A small pro pack unlocks with a license code.

Each problem ships with:

- statement + samples that deliberately avoid the classic pitfall
- a correct solver
- a brute-force oracle used by the finder
- shrink helpers so the counterexample stays tiny

---

## Feedback from a first user

A friend who has been grinding competitive-programming style problems tried the live site.

- They said the first-step gate stops the “I already know this, I’ll just write the solution” reflex that later leaves them blank on a new variant.
- They would pay if there were more problems and filters by pattern / difficulty.
- They asked for a way to check an approach while still writing code (not only at the end). That is on the roadmap; it is intentionally not the identity of the tool yet.

That single real session is the current evidence that the idea is useful to at least one person who already cares about this skill.

---

## Tech stack

- **Backend:** FastAPI, SQLite (per-learner sessions, failure profiles, reviews)
- **Runner:** AST-limited Python execution with time and memory caps
- **Finder:** oracle + budgeted search + shrink
- **LLM (optional):** Ollama or any OpenAI-compatible API; Gemma used in local tests
- **Deploy:** Docker + Render Blueprint (`render.yaml`)
- **Frontend:** single static page, no framework

---

## Quick start (local)

```bash
git clone https://github.com/meenanoolu/firststep.git
cd firststep
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit only if you want a model
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

Run the tests:

```bash
pytest -q
```

---

## Deploy on Render

The repo contains `render.yaml`. Create a Blueprint from the GitHub repo (or connect the repo and use the existing service).  

Important env vars already set in the Blueprint:

- `DB_PATH=/data/firststep.db`
- `LLM_PROVIDER=none` (safe default)
- concurrency and daily submit caps

To attach a hosted open model later, set `LLM_PROVIDER=openai`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in the Render dashboard.

---

## Project layout

```
app/
  main.py            # FastAPI routes
  firststep.py       # first-step classifier (rules + optional model)
  counterexample.py  # finder + shrinker
  runner.py          # sandboxed execution
  llm.py             # Ollama / OpenAI-compatible client
  leakcheck.py       # stops solution leakage
  store.py           # SQLite learner store
  problems/          # problem bank + pro pack
  static/            # UI
tests/               # unit + API tests
eval/                # offline evaluation helpers
data/                # labelled first-step examples (train/test)
render.yaml          # Render Blueprint
Dockerfile
```

---

## Limits (honest)

- Only a handful of problems so far.
- The transfer / “can you still solve a twist?” idea is sketched but not yet a full product feature.
- One real user has tried it.
- Local model path is slower on CPU (several seconds per first-step or explanation). Production demo uses the rule fallback for speed.


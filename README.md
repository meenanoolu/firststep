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
| `LLM_PROVIDER=tinker` | **Production setting.** The LoRA-tuned Qwen3-8B first-step classifier, served by Tinker's OpenAI-compatible endpoint. It does one job (classify the first step). Hints and explanations stay static and leak-checked. |

When the model is used, every reply is leak-checked. If the model fails or is unreachable the tool still works.

Local example (already tested with Gemma):

```bash
ollama pull gemma2:2b          # or whatever tag you prefer
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=gemma2:2b
uvicorn app.main:app --reload
```

On Render the live service runs `LLM_PROVIDER=tinker`: each first-step sentence is classified by the fine-tuned model, with an 8 second timeout. On any error, timeout or unexpected output the deterministic rules answer instead, so the learner is never blocked. `/api/health` reports which backend is active and `/api/stats` shows how many model calls were accepted or fell back.

---

## 🤖 Tinker Fine-Tuning & Evaluation

I used [Tinker](https://tinker-docs.thinkingmachines.ai/) to fine-tune `Qwen/Qwen3-8B` (LoRA, rank 16) to classify a learner's first step into `restate | small_example | brute_force | observation | too_vague`. The tuned model runs live in the deployed app; deterministic rules are the fallback.

### Results
| Run | Training | Test | Rules | Base model | Tuned model | Viable accuracy |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 (pilot) | 60 | 20 | n/a | 20% | 55% | 80% |
| 2 | 250 | 50 | 40% | 56% | 70% | 80% |
| 3 | 250 | 50 | 40% | 56% | 72% | 82% |
| **4 (live model)** | 250 | 50 | 40% | 56% | **100%** | **100%** |

**What changed in Run 4:** Runs 1-3 made one optimizer step per epoch (4 steps in total). Run 4 uses minibatches of 16 for 3 epochs (48 steps).

**Unseen problems:** the Run 4 checkpoint scored **40/40 (95% CI 91-100%)** on `data/firststep_unseen.jsonl`, written for two problems that never appear in training (`balanced-brackets`, `range-sum-queries`). Rules score 16/40 (40%) on the same file.

**Limits.** Both test sets are small and hand-written, and the unseen set is cleaner than real learner text. Treat these numbers as evidence that the approach works, not a final accuracy. Next step: score real first steps collected by the live app.

### How the model is used in production
- Render calls the saved sampler checkpoint through Tinker's OpenAI-compatible `/completions` endpoint, using the exact prompt format it was trained on (`LLM_PROVIDER=tinker`).
- The model only classifies. Hints and counterexample explanations stay static and leak-checked.
- Any timeout, error or unexpected output falls back to the rules, so a learner is never blocked. Tinker's endpoint is in beta and meant for low traffic, which is why the fallback matters.
- `/api/health` shows the active backend and `/api/stats` shows accepted vs fallback model calls.

### Inspect the experiment artifacts
- [`tinker_ft/train_firststep.py`](./tinker_ft/train_firststep.py): training and evaluation
- [`tinker_ft/eval_checkpoint.py`](./tinker_ft/eval_checkpoint.py): score a saved checkpoint on any labelled file
- [`tinker_ft/RESULTS.md`](./tinker_ft/RESULTS.md): full experiment log
- [`runs/v2_minibatch/`](./runs/v2_minibatch/): Run 4 metrics, predictions, confusion matrix
- [`runs/main_experiment/`](./runs/main_experiment/): Run 3 records
- [`scripts/audit_tinker_data.py`](./scripts/audit_tinker_data.py): dataset audit
- [`data/`](./data/): train, test and unseen-problem sets

### Reproduce
```bash
git clone https://github.com/meenanoolu/firststep.git
cd firststep
pip install -r requirements.txt
pip install tinker
export TINKER_API_KEY=your_api_key_here
python -m tinker_ft.train_firststep        # trains, evaluates, prints the tinker:// sampler path

export TINKER_SAMPLER_PATH=tinker://...    # the path printed above
python -m tinker_ft.eval_checkpoint data/firststep_unseen.jsonl
```

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
- `LLM_PROVIDER=tinker` (falls back to rules if `LLM_MODEL` or the key is missing)
- concurrency and daily submit caps

To run the Tinker model, set two secrets in the Render dashboard (the Blueprint already sets `LLM_PROVIDER=tinker` and `LLM_TIMEOUT_S=8`):

- `LLM_API_KEY` = your Tinker API key
- `LLM_MODEL` = the `tinker://.../sampler_weights/...` path printed by `python -m tinker_ft.train_firststep` (or listed by `python -m tinker_ft.find_sampler_path`)

Leave `LLM_MODEL` empty and the service runs on rules alone. Note: a Render service with a disk does not get zero-downtime deploys, so a deploy causes a short restart.

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
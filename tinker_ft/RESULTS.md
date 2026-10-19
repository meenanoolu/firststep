# Tinker fine-tune results

Task: classify a learner's first-step sentence into  
`restate | small_example | brute_force | observation | too_vague`

Method: LoRA SFT via [Tinker](https://tinker-docs.thinkingmachines.ai/)

I ran the fine-tune **twice** (two separate experiments, not continued training).

## Run 1 — pilot (small data)

Data: 60 train / 20 held-out

| Method | Accuracy | Viable accuracy | Latency (sec/call) |
|--------|----------|-----------------|--------------------|
| Base model (before fine-tune) | 0.20 | 0.45 | 7.22 |
| **Tuned model (after Tinker LoRA)** | **0.55** | **0.80** | 7.11 |

## Run 2 — main result (more data)

Data: **250** train / **50** held-out (`data/firststep_train.jsonl`, `data/firststep_test.jsonl`)

| Method | Accuracy | Viable accuracy | Latency (sec/call) |
|--------|----------|-----------------|--------------------|
| Base model (before fine-tune) | 0.56 | 0.64 | 2.07 |
| **Tuned model (after Tinker LoRA)** | **0.70** | **0.80** | 2.15 |

Accuracy +0.14; viable-vs-not +0.16; latency essentially unchanged.

The **second run** is the main result (larger held-out set). Both times the tuned model beat the base model on the same task setup.

Reproduce run 2:

```bash
pip install tinker
export TINKER_API_KEY=...
python -m tinker_ft.train_firststep
# Tinker fine-tune results

Task: classify a learner's first-step sentence into  
`restate | small_example | brute_force | observation | too_vague`

Data: `data/firststep_train.jsonl` (**250**) → train, `data/firststep_test.jsonl` (**50**) → eval  
Method: LoRA SFT via [Tinker](https://tinker-docs.thinkingmachines.ai/)

| Method | Accuracy | Viable accuracy | Latency (sec/call) |
|--------|----------|-----------------|--------------------|
| Base model (before fine-tune) | 0.56 | 0.64 | 2.07 |
| **Tuned model (after Tinker LoRA)** | **0.70** | **0.80** | 2.15 |

Accuracy +0.14; viable-vs-not +0.16; latency essentially unchanged.

Reproduce:

```bash
pip install tinker
export TINKER_API_KEY=...
python -m tinker_ft.train_firststep
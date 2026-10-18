# Tinker fine-tune results

Task: classify a learner's first-step sentence into  
`restate | small_example | brute_force | observation | too_vague`

Data: `data/firststep_train.jsonl` (60) → train, `data/firststep_test.jsonl` (20) → eval  
Method: LoRA SFT via [Tinker](https://tinker-docs.thinkingmachines.ai/)

| Method | Accuracy | Viable accuracy | Latency (sec/call) |
|--------|----------|-----------------|--------------------|
| Base model (before fine-tune) | 0.20 | 0.45 | 7.22 |
| **Tuned model (after Tinker LoRA)** | **0.55** | **0.80** | 7.11 |

Accuracy more than doubled. Viable-vs-not accuracy: 0.45 → 0.80.  
Latency essentially unchanged.

Reproduce:

```bash
pip install tinker
export TINKER_API_KEY=...
python -m tinker_ft.train_firststep
```

Production FirstStep still defaults to deterministic rules (`LLM_PROVIDER=none`).
The tuned adapter is an optional upgrade path, not a hard dependency.

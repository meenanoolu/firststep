# Tinker Fine-Tuning Results

Task: Classify a learner's first-step sentence into:  
`restate | small_example | brute_force | observation | too_vague`

Method: LoRA SFT via [Tinker](https://tinker-docs.thinkingmachines.ai/)

We maintained an iterative experimental log across three distinct fine-tuning executions to ensure transparency, reproducibility, and rigorous data scaling.

## Summary of Experiments

| Run | Training Data | Held-Out Test Data | Base Model Accuracy | Tuned Model Accuracy | Viable Accuracy | Latency (sec/call) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run 1 (Pilot)** | 60 examples | 20 examples | 20% | 55% | 80% | 7.11 |
| **Run 2 (Main Historical)** | 250 examples | 50 examples | 56% | 70% | 80% | 2.15 |
| **Run 3 (Live Verification)** | 250 examples | 50 examples | 56% | **72%** | **82%** | 4.78 |

---

## Detailed Run Breakdowns

### Run 1 — Initial Pilot
* **Purpose:** Proved the fine-tuning training loop and validated prompt formatting before scaling up data collection.
* **Outcome:** Reached 55% exact-label accuracy from a baseline of 20%, justifying expansion to a larger dataset.

### Run 2 — Scaled Experiment
* **Purpose:** Scaled training volume to 250 rows and evaluated against a controlled 50-item test split (`data/firststep_train.jsonl`, `data/firststep_test.jsonl`).
* **Outcome:** Achieved 70% exact-label accuracy, establishing the primary performance benchmark for the project.

### Run 3 — Live-Verified Execution (Fresh Verification)
* **Purpose:** Re-executed the complete training and evaluation script live via the Tinker SDK to generate fresh prediction logs and test pipeline integrity.
* **Outcome:** Reached **72% exact-label accuracy** and **82% viable-intent accuracy**, generating the prediction logs and confusion matrices stored in `runs/main_experiment/`.

---

## Per-Class Performance & Error Analysis (Run 3)

### Confusion Matrix (Test Set: 50 Examples)
| True \ Predicted | Restate | Small Example | Brute Force | Observation | Too Vague |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Restate** | **8** | 1 | 0 | 0 | 1 |
| **Small Example** | 0 | **8** | 1 | 1 | 0 |
| **Brute Force** | 0 | 1 | **7** | 1 | 1 |
| **Observation** | 1 | 0 | 0 | **7** | 2 |
| **Too Vague** | 1 | 0 | 0 | 3 | **6** |

### Key Observations
1. **Viable Intent Boundaries:** The tuned model reliably distinguishes concrete starting moves (`small_example`, `brute_force`) from unhelpful vagueness (`too_vague`), reaching 82% viable accuracy.
2. **Primary Failure Mode:** The most common misclassification occurs between `too_vague` and `observation` when students provide partial insights that lack explicit next steps.

## Baselines & Limitations
* **Deterministic Rules Baseline:** 40% exact-label accuracy on the 50-item test set.
* **Production Status:** The hosted application defaults to deterministic rules (`LLM_PROVIDER=none`) for reliability, while the Tinker-tuned model serves as an optional high-precision upgrade path.
* **Test Scale:** Evaluations utilize a strict 50-item held-out split to adhere to API budgeting constraints.

## Reproduction Instructions
To reproduce the live-verified main experiment:

```bash
pip install tinker
export TINKER_API_KEY=your_api_key_here
python -m tinker_ft.train_firststep
"""Fine-tune + evaluate first-step classifier with Tinker.

Arms on data/firststep_test.jsonl:
  base  — model before training
  tuned — after LoRA SFT on data/firststep_train.jsonl

Reports accuracy, viable accuracy, latency, saves prediction logs and confusion matrices.
Production FirstStep still uses rules by default.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import tinker
from tinker import types

ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL = os.environ.get("TINKER_MODEL", "Qwen/Qwen3-8B")
EPOCHS = int(os.environ.get("TINKER_EPOCHS", "4"))
LR = float(os.environ.get("TINKER_LR", "1e-4"))
RANK = int(os.environ.get("TINKER_RANK", "16"))
LABELS = ["restate", "small_example", "brute_force", "observation", "too_vague"]
VIABLE = {"brute_force", "small_example", "observation"}


def rows(name: str) -> list[dict]:
    path = ROOT / "data" / name
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def prompt(r: dict) -> str:
    return (
        f"Problem: {r['statement']}\n"
        f"Learner's first step: {r['text']}\n"
        f"Classify as one of {', '.join(LABELS)}.\n"
        f"Label:"
    )


async def evaluate(sampling_client, tok, test: list[dict], split_name: str) -> tuple[dict, list[dict], dict]:
    ok = viable_ok = 0
    t0 = time.time()
    predictions = []
    confusion_matrix = {l: {l2: 0 for l2 in LABELS} for l in LABELS}

    for idx, r in enumerate(test):
        p = types.ModelInput.from_ints(tok.encode(prompt(r)))
        out = await sampling_client.sample_async(
            prompt=p,
            num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=6, temperature=0.0, stop=["\n"]),
        )
        tokens = out.sequences[0].tokens if out.sequences else []
        pred = tok.decode(tokens).strip().split()[0] if tokens else ""
        
        if pred not in LABELS:
            pred = "too_vague"

        true_label = r["label"]
        is_correct = (pred == true_label)
        is_viable_correct = ((pred in VIABLE) == (true_label in VIABLE))

        ok += is_correct
        viable_ok += is_viable_correct

        if true_label in confusion_matrix and pred in confusion_matrix[true_label]:
            confusion_matrix[true_label][pred] += 1

        predictions.append({
            "id": r.get("id", idx),
            "statement": r["statement"],
            "sentence": r["text"],
            "true_label": true_label,
            "predicted_label": pred,
            "correct": is_correct,
            "viable_correct": is_viable_correct
        })

    n = max(len(test), 1)
    metrics = {
        "split": split_name,
        "acc": round(ok / n, 4),
        "viable_acc": round(viable_ok / n, 4),
        "sec_per_call": round((time.time() - t0) / n, 4),
        "n": n,
    }
    return metrics, predictions, confusion_matrix


async def main() -> None:
    train, test = rows("firststep_train.jsonl"), rows("firststep_test.jsonl")
    print(f"train={len(train)} test={len(test)} model={BASE_MODEL} epochs={EPOCHS} rank={RANK}")

    output_dir = ROOT / "runs" / "main_experiment"
    output_dir.mkdir(parents=True, exist_ok=True)

    svc = tinker.ServiceClient()
    # Use the async version of create_lora_training_client to prevent deadlocks
    tc = await svc.create_lora_training_client_async(base_model=BASE_MODEL, rank=RANK)
    tok = tc.get_tokenizer()

    base = tc.save_weights_and_get_sampling_client(name="base")
    base_m, base_preds, base_cm = await evaluate(base, tok, test, "base")
    print("base :", base_m)

    data = []
    for r in train:
        pt, ct = tok.encode(prompt(r)), tok.encode(" " + r["label"] + "\n")
        full = pt + ct
        data.append(
            types.Datum(
                model_input=types.ModelInput.from_ints(tokens=full[:-1]),
                loss_fn_inputs=dict(
                    weights=[0.0] * (len(pt) - 1) + [1.0] * len(ct),
                    target_tokens=full[1:],
                ),
            )
        )

    for ep in range(EPOCHS):
        fb = await tc.forward_backward_async(data=data, loss_fn="cross_entropy")
        await fb.result_async()
        op = await tc.optim_step_async(types.AdamParams(learning_rate=LR))
        await op.result_async()
        print(f"epoch {ep + 1}/{EPOCHS} done")

    tuned = tc.save_weights_and_get_sampling_client(name="tuned")
    tuned_m, tuned_preds, tuned_cm = await evaluate(tuned, tok, test, "tuned")
    print("tuned:", tuned_m)

    metrics_payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "config": {
            "base_model": BASE_MODEL,
            "epochs": EPOCHS,
            "learning_rate": LR,
            "rank": RANK,
            "train_size": len(train),
            "test_size": len(test)
        },
        "base_metrics": base_m,
        "tuned_metrics": tuned_m
    }

    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(output_dir / "predictions.jsonl", "w", encoding="utf-8") as f:
        for p in tuned_preds:
            f.write(json.dumps(p) + "\n")

    with open(output_dir / "confusion_matrix.json", "w", encoding="utf-8") as f:
        json.dump(tuned_cm, f, indent=2)

    print(f"\nSaved full run records, predictions, and confusion matrix to {output_dir}")

    print("\n=== copy into tinker_ft/RESULTS.md ===")
    print(f"| Method | Accuracy | Viable accuracy | Latency (sec/call) |")
    print(f"| ------ | -------- | --------------- | ------------------ |")
    print(f"| Base model (before fine-tune) | {base_m['acc']} | {base_m['viable_acc']} | {base_m['sec_per_call']} |")
    print(f"| **Tuned model (after Tinker LoRA)** | **{tuned_m['acc']}** | **{tuned_m['viable_acc']}** | {tuned_m['sec_per_call']} |")
    print(f"Data: train={len(train)} test={len(test)}")


if __name__ == "__main__":
    asyncio.run(main())
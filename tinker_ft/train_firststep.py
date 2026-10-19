"""Fine-tune + evaluate first-step classifier with Tinker.

Arms on data/firststep_test.jsonl:
  base  — model before training
  tuned — after LoRA SFT on data/firststep_train.jsonl

Reports accuracy, viable accuracy, latency.
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


async def evaluate(sampling_client, tok, test: list[dict]) -> dict:
    ok = viable_ok = 0
    t0 = time.time()
    for r in test:
        p = types.ModelInput.from_ints(tok.encode(prompt(r)))
        out = await sampling_client.sample_async(
            prompt=p,
            num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=6, temperature=0.0, stop=["\n"]),
        )
        tokens = out.sequences[0].tokens if out.sequences else []
        pred = tok.decode(tokens).strip().split()[0] if tokens else ""
        ok += pred == r["label"]
        viable_ok += (pred in VIABLE) == (r["label"] in VIABLE)
    n = max(len(test), 1)
    return {
        "acc": round(ok / n, 4),
        "viable_acc": round(viable_ok / n, 4),
        "sec_per_call": round((time.time() - t0) / n, 4),
        "n": n,
    }


async def main() -> None:
    train, test = rows("firststep_train.jsonl"), rows("firststep_test.jsonl")
    print(f"train={len(train)} test={len(test)} model={BASE_MODEL} epochs={EPOCHS} rank={RANK}")

    svc = tinker.ServiceClient()
    tc = svc.create_lora_training_client(base_model=BASE_MODEL, rank=RANK)
    tok = tc.get_tokenizer()

    base = tc.save_weights_and_get_sampling_client(name="base")
    base_m = await evaluate(base, tok, test)
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
    tuned_m = await evaluate(tuned, tok, test)
    print("tuned:", tuned_m)

    print("\n=== copy into tinker_ft/RESULTS.md ===")
    print(f"| Method | Accuracy | Viable accuracy | Latency (sec/call) |")
    print(f"| ------ | -------- | --------------- | ------------------ |")
    print(f"| Base model (before fine-tune) | {base_m['acc']} | {base_m['viable_acc']} | {base_m['sec_per_call']} |")
    print(f"| **Tuned model (after Tinker LoRA)** | **{tuned_m['acc']}** | **{tuned_m['viable_acc']}** | {tuned_m['sec_per_call']} |")
    print(f"Data: train={len(train)} test={len(test)}")


if __name__ == "__main__":
    asyncio.run(main())
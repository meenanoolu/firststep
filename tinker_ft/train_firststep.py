"""Fine-tune a small open model with Tinker to classify a learner's first step, and compare with baselines.

STATUS: written from Tinker's SDK cheatsheet (create_lora_training_client / forward_backward_async / optim_step_async /
save_weights_and_get_sampling_client / sample_async). NOT RUN yet: needs TINKER_API_KEY and the $10 credit.
Check model names on the Models & Pricing page first (the cheatsheet example uses Qwen/Qwen3-8B; pick a smaller one
to keep cost low). Claim the Tinker credit only when you are ready to run this.

Compare three arms on data/firststep_test.jsonl (held-out problems AND templates):
  rules   : app.firststep.classify_rules          (free, instant)
  base    : the same model BEFORE training, prompted with the same format
  tuned   : after LoRA SFT on data/firststep_train.jsonl
Report accuracy, viable-vs-not accuracy, latency per call, and dollars spent. If tuned does not beat rules, say so.
"""
import asyncio
import json
import os
import time
from pathlib import Path

import tinker
from tinker import types

ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL = os.environ.get("TINKER_MODEL", "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16")
EPOCHS, LR = 3, 1e-4
LABELS = ["restate", "small_example", "brute_force", "observation", "too_vague"]


def rows(name):
    return [json.loads(x) for x in (ROOT / "data" / name).read_text().splitlines() if x.strip()]


def prompt(r):
    return (f"Problem: {r['statement']}\nLearner's first step: {r['text']}\n"
            f"Classify as one of {', '.join(LABELS)}.\nLabel:")


async def evaluate(sampling_client, tok, test):
    ok = viable_ok = 0
    t0 = time.time()
    viable = {"brute_force", "small_example", "observation"}
    for r in test:
        p = types.ModelInput.from_ints(tok.encode(prompt(r)))
        out = await sampling_client.sample_async(prompt=p, num_samples=1,
                                                 sampling_params=types.SamplingParams(max_tokens=6, temperature=0.0, stop=["\n"]))
        pred = tok.decode(out.sequences[0].tokens).strip().split()[0] if out.sequences[0].tokens else ""
        ok += pred == r["label"]
        viable_ok += (pred in viable) == (r["label"] in viable)
    n = len(test)
    return {"acc": ok / n, "viable_acc": viable_ok / n, "sec_per_call": (time.time() - t0) / n}


async def main():
    train, test = rows("firststep_train.jsonl"), rows("firststep_test.jsonl")
    svc = tinker.ServiceClient()
    tc = svc.create_lora_training_client(base_model=BASE_MODEL, rank=16)
    tok = tc.get_tokenizer()
    base = tc.save_weights_and_get_sampling_client(name="base")
    print("base :", await evaluate(base, tok, test))
    data = []
    for r in train:
        pt, ct = tok.encode(prompt(r)), tok.encode(" " + r["label"] + "\n")
        full = pt + ct
        data.append(types.Datum(
            model_input=types.ModelInput.from_ints(tokens=full[:-1]),
            loss_fn_inputs=dict(weights=[0.0] * (len(pt) - 1) + [1.0] * len(ct), target_tokens=full[1:])))
    for ep in range(EPOCHS):
        fb = await tc.forward_backward_async(data=data, loss_fn="cross_entropy")
        await fb.result_async()
        op = await tc.optim_step_async(types.AdamParams(learning_rate=LR))
        await op.result_async()
        print("epoch", ep + 1, "done")
    tuned = tc.save_weights_and_get_sampling_client(name="tuned")
    print("tuned:", await evaluate(tuned, tok, test))


if __name__ == "__main__":
    asyncio.run(main())
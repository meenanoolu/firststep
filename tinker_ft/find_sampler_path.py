"""List the sampler checkpoints saved under your Tinker account, so you can copy the tinker:// path
of the model you already trained (no retraining needed). Run:  python -m tinker_ft.find_sampler_path"""
import asyncio

import tinker


async def main() -> None:
    rest = tinker.ServiceClient().create_rest_client()
    resp = await rest.list_user_checkpoints_async(limit=100)
    items = getattr(resp, "checkpoints", resp)
    found = False
    for c in items:
        if "sampler" in str(getattr(c, "checkpoint_type", "")).lower():
            found = True
            print(getattr(c, "tinker_path", c))
    if not found:
        print("No sampler checkpoints found. Run: python -m tinker_ft.train_firststep")


if __name__ == "__main__":
    asyncio.run(main())
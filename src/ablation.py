import csv
import os

import numpy as np

from model import GPTConfig
from train import BATCH_SIZE, CKPT_DIR, DATA_DIR, LEARNING_RATE, train_model

BLOCK_SIZE = 256
MAX_ITERS = 1500
EVAL_INTERVAL = 150
EVAL_ITERS = 50

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "ablation_results.csv")

VARIANTS = {
    "baseline": dict(use_pos_emb=True, use_causal_mask=True),
    "no_pos_emb": dict(use_pos_emb=False, use_causal_mask=True),
    "no_causal_mask": dict(use_pos_emb=True, use_causal_mask=False),
}


def main():
    vocab_size = len(np.load(os.path.join(DATA_DIR, "vocab.npy")))
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    rows = []
    for name, flags in VARIANTS.items():
        print(f"\n=== ablation variant: {name} ({flags}) ===")
        config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE, **flags)
        ckpt_path = os.path.join(CKPT_DIR, f"ablation_{name}.pt")
        history = train_model(
            config,
            ckpt_path,
            max_iters=MAX_ITERS,
            eval_interval=EVAL_INTERVAL,
            eval_iters=EVAL_ITERS,
            batch_size=BATCH_SIZE,
            lr=LEARNING_RATE,
            resume=True,
        )
        for it, train_loss, val_loss in history:
            rows.append({"variant": name, "iter": it, "train_loss": train_loss, "val_loss": val_loss})

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["variant", "iter", "train_loss", "val_loss"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nsaved results to {RESULTS_PATH}")
    print("\nfinal loss per variant:")
    for name in VARIANTS:
        last = [r for r in rows if r["variant"] == name][-1]
        print(f"  {name}: train {last['train_loss']:.4f}, val {last['val_loss']:.4f}")


if __name__ == "__main__":
    main()

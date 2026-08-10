import csv
import json
import math
import os
import time

import numpy as np

from model import GPT, GPTConfig
from train import BATCH_SIZE, CKPT_DIR, DATA_DIR, LEARNING_RATE, load_data, train_model

BLOCK_SIZE = 256
N_LAYER = 4
N_HEAD = 4
N_EMBD = 256
MAX_ITERS = 1500
EVAL_INTERVAL = 150
EVAL_ITERS = 50

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "tokenizer_compare.csv")


def load_bpe_data():
    train_data = np.memmap(os.path.join(DATA_DIR, "train_bpe.bin"), dtype=np.uint16, mode="r")
    val_data = np.memmap(os.path.join(DATA_DIR, "val_bpe.bin"), dtype=np.uint16, mode="r")
    with open(os.path.join(DATA_DIR, "bpe_meta.json")) as f:
        meta = json.load(f)
    return train_data, val_data, meta["vocab_size"], meta["compression_ratio"]


def run_variant(name, vocab_size, chars_per_token, train_data, val_data):
    print(f"\n=== tokenizer: {name} (vocab_size={vocab_size}, chars/token={chars_per_token:.3f}) ===")
    config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE, n_layer=N_LAYER, n_head=N_HEAD, n_embd=N_EMBD)
    n_params = sum(p.numel() for p in GPT(config).parameters())

    ckpt_path = os.path.join(CKPT_DIR, f"tokcompare_{name}.pt")
    start = time.time()
    history = train_model(
        config,
        ckpt_path,
        max_iters=MAX_ITERS,
        eval_interval=EVAL_INTERVAL,
        eval_iters=EVAL_ITERS,
        batch_size=BATCH_SIZE,
        lr=LEARNING_RATE,
        resume=False,
        train_data=train_data,
        val_data=val_data,
    )
    wall_time_sec = time.time() - start

    final_train, final_val = history[-1][1], history[-1][2]
    # bits-per-character: normalizes cross-entropy across different vocab sizes/token
    # granularities so char-level and BPE runs can be compared on equal footing.
    bpc = final_val / chars_per_token / math.log(2)
    context_chars = BLOCK_SIZE * chars_per_token

    return {
        "tokenizer": name,
        "vocab_size": vocab_size,
        "n_params": n_params,
        "chars_per_token": round(chars_per_token, 3),
        "context_chars": round(context_chars, 1),
        "wall_time_sec": round(wall_time_sec, 1),
        "train_loss": round(final_train, 4),
        "val_loss": round(final_val, 4),
        "bits_per_char": round(bpc, 4),
    }


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    char_train, char_val, char_vocab_size = load_data()
    bpe_train, bpe_val, bpe_vocab_size, compression_ratio = load_bpe_data()

    rows = [
        run_variant("char", char_vocab_size, 1.0, char_train, char_val),
        run_variant("bpe", bpe_vocab_size, compression_ratio, bpe_train, bpe_val),
    ]

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nsaved results to {RESULTS_PATH}")
    print("\nsummary (bits_per_char is the fair cross-tokenizer comparison metric):")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()

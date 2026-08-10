import csv
import os
import time

import numpy as np
import optuna
import torch

from model import GPT, GPTConfig
from train import BATCH_SIZE, CKPT_DIR, DATA_DIR, LEARNING_RATE, train_model

BLOCK_SIZE = 256
MAX_ITERS = 800
EVAL_INTERVAL = 200
EVAL_ITERS = 30
N_TRIALS = 6

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "search_results.csv")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def count_params(model):
    return sum(p.numel() for p in model.parameters())


def objective(trial, vocab_size):
    n_layer = trial.suggest_categorical("n_layer", [2, 4, 6, 8])
    n_head = trial.suggest_categorical("n_head", [2, 4, 6])
    head_size = trial.suggest_categorical("head_size", [32, 48, 64])
    n_embd = n_head * head_size

    config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE, n_layer=n_layer, n_head=n_head, n_embd=n_embd)
    n_params = count_params(GPT(config))

    if DEVICE == "cuda":
        torch.cuda.reset_peak_memory_stats()
    start = time.time()

    ckpt_path = os.path.join(CKPT_DIR, f"search_trial{trial.number}.pt")
    history = train_model(
        config,
        ckpt_path,
        max_iters=MAX_ITERS,
        eval_interval=EVAL_INTERVAL,
        eval_iters=EVAL_ITERS,
        batch_size=BATCH_SIZE,
        lr=LEARNING_RATE,
        resume=False,
    )

    wall_time_sec = time.time() - start
    peak_mem_mb = torch.cuda.max_memory_allocated() / 1e6 if DEVICE == "cuda" else 0
    final_train, final_val = history[-1][1], history[-1][2]

    trial.set_user_attr("n_embd", n_embd)
    trial.set_user_attr("n_params", n_params)
    trial.set_user_attr("wall_time_sec", wall_time_sec)
    trial.set_user_attr("peak_mem_mb", peak_mem_mb)
    trial.set_user_attr("train_loss", final_train)

    return final_val


def main():
    vocab_size = len(np.load(os.path.join(DATA_DIR, "vocab.npy")))
    os.makedirs(RESULTS_DIR, exist_ok=True)

    study = optuna.create_study(direction="minimize")
    study.optimize(lambda t: objective(t, vocab_size), n_trials=N_TRIALS)

    rows = []
    for t in study.trials:
        rows.append(
            {
                "trial": t.number,
                "n_layer": t.params["n_layer"],
                "n_head": t.params["n_head"],
                "n_embd": t.user_attrs["n_embd"],
                "n_params": t.user_attrs["n_params"],
                "wall_time_sec": round(t.user_attrs["wall_time_sec"], 1),
                "peak_mem_mb": round(t.user_attrs["peak_mem_mb"], 1),
                "train_loss": round(t.user_attrs["train_loss"], 4),
                "val_loss": round(t.value, 4),
            }
        )

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nsaved results to {RESULTS_PATH}")
    print(f"\nbest trial: #{study.best_trial.number} {study.best_params} val_loss={study.best_value:.4f}")
    print("\nall trials (sorted by val_loss):")
    for r in sorted(rows, key=lambda r: r["val_loss"]):
        print(r)


if __name__ == "__main__":
    main()

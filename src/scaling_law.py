import csv
import os

import numpy as np

from model import GPT, GPTConfig
from train import BATCH_SIZE, CKPT_DIR, LEARNING_RATE, load_data, train_model

BLOCK_SIZE = 256
MAX_ITERS = 600
EVAL_INTERVAL = 150
EVAL_ITERS = 25

MODEL_SIZES = {
    "small": dict(n_layer=2, n_head=4, n_embd=128),
    "medium": dict(n_layer=4, n_head=4, n_embd=256),
    "large": dict(n_layer=6, n_head=6, n_embd=384),
}
DATA_FRACTIONS = [0.25, 0.5, 1.0]

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "scaling_law.csv")


def fit_loglog_slope(xs, ys):
    log_x = np.log(xs)
    log_y = np.log(ys)
    slope, intercept = np.polyfit(log_x, log_y, 1)
    return slope


def main():
    full_train, val_data, vocab_size = load_data()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows = []
    for size_name, size_cfg in MODEL_SIZES.items():
        config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE, **size_cfg)
        n_params = sum(p.numel() for p in GPT(config).parameters())

        for frac in DATA_FRACTIONS:
            n_train = int(len(full_train) * frac)
            train_subset = full_train[:n_train]

            run_name = f"{size_name}_frac{int(frac * 100)}"
            print(f"\n=== {run_name}: n_params={n_params:,}, train_tokens={n_train:,} ===")
            ckpt_path = os.path.join(CKPT_DIR, f"scaling_{run_name}.pt")
            history = train_model(
                config,
                ckpt_path,
                max_iters=MAX_ITERS,
                eval_interval=EVAL_INTERVAL,
                eval_iters=EVAL_ITERS,
                batch_size=BATCH_SIZE,
                lr=LEARNING_RATE,
                resume=False,
                train_data=train_subset,
                val_data=val_data,
            )
            final_val = history[-1][2]
            rows.append(
                {
                    "model_size": size_name,
                    "n_params": n_params,
                    "data_fraction": frac,
                    "train_tokens": n_train,
                    "val_loss": round(final_val, 4),
                }
            )

            with open(RESULTS_PATH, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

    print(f"\nsaved results to {RESULTS_PATH}")
    print("\nall runs:")
    for r in rows:
        print(r)

    # rough log-log slopes: how loss scales with params (at full data) and with
    # data size (at the largest model) -- illustrative only, just 3 points per axis
    full_data_rows = [r for r in rows if r["data_fraction"] == 1.0]
    params_xs = [r["n_params"] for r in full_data_rows]
    params_ys = [r["val_loss"] for r in full_data_rows]
    param_slope = fit_loglog_slope(params_xs, params_ys)

    largest_model_rows = [r for r in rows if r["model_size"] == "large"]
    data_xs = [r["train_tokens"] for r in largest_model_rows]
    data_ys = [r["val_loss"] for r in largest_model_rows]
    data_slope = fit_loglog_slope(data_xs, data_ys)

    print(f"\nloss ~ n_params^({param_slope:.3f})  (at data_fraction=1.0, 3 points)")
    print(f"loss ~ train_tokens^({data_slope:.3f})  (at model_size=large, 3 points)")


if __name__ == "__main__":
    main()

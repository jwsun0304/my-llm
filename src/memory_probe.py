import csv
import os

import torch

from model import GPT, GPTConfig
from train import get_batch, load_data

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "memory_probe.csv")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BLOCK_SIZE = 256
BATCH_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]


def probe_batch_size(config, train_data, val_data, batch_size):
    model = GPT(config).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    try:
        x, y = get_batch("train", train_data, val_data, config.block_size, batch_size)
        _, loss = model(x, y)
        loss.backward()
        optimizer.step()
        peak_mem_mb = torch.cuda.max_memory_allocated() / 1e6
        status = "ok"
    except torch.cuda.OutOfMemoryError:
        peak_mem_mb = None
        status = "oom"
    finally:
        del model, optimizer
        torch.cuda.empty_cache()
    return status, peak_mem_mb


def main():
    if DEVICE != "cuda":
        print("no GPU available, skipping memory probe")
        return

    train_data, val_data, vocab_size = load_data()
    config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE, n_layer=8, n_head=8, n_embd=512)
    n_params = sum(p.numel() for p in GPT(config).parameters())
    print(f"probing config: n_layer=8, n_head=8, n_embd=512, block_size={BLOCK_SIZE} ({n_params:,} params)")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []
    for bs in BATCH_SIZES:
        status, peak_mem_mb = probe_batch_size(config, train_data, val_data, bs)
        msg = f"batch_size {bs}: {status}"
        if peak_mem_mb is not None:
            msg += f", peak mem {peak_mem_mb:.1f} MB"
        print(msg)
        rows.append({"batch_size": bs, "status": status, "peak_mem_mb": peak_mem_mb})
        if status == "oom":
            break

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["batch_size", "status", "peak_mem_mb"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nsaved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()

import os

import numpy as np
import torch

from model import GPT, GPTConfig

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CKPT_DIR = os.environ.get("CKPT_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints"))

BATCH_SIZE = 64
BLOCK_SIZE = 256
MAX_ITERS = 5000
EVAL_INTERVAL = 250
EVAL_ITERS = 100
LEARNING_RATE = 3e-4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def get_batch(split, train_data, val_data, block_size, batch_size):
    data = train_data if split == "train" else val_data
    ix = torch.randint(len(data) - block_size, (batch_size,))
    x = torch.stack([torch.from_numpy(data[i : i + block_size].astype(np.int64)) for i in ix])
    y = torch.stack([torch.from_numpy(data[i + 1 : i + 1 + block_size].astype(np.int64)) for i in ix])
    return x.to(DEVICE), y.to(DEVICE)


@torch.no_grad()
def estimate_loss(model, train_data, val_data, eval_iters, block_size, batch_size):
    out = {}
    model.eval()
    for split in ["train", "val"]:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            x, y = get_batch(split, train_data, val_data, block_size, batch_size)
            _, loss = model(x, y)
            losses[k] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


def load_data():
    train_data = np.memmap(os.path.join(DATA_DIR, "train.bin"), dtype=np.uint16, mode="r")
    val_data = np.memmap(os.path.join(DATA_DIR, "val.bin"), dtype=np.uint16, mode="r")
    vocab_size = len(np.load(os.path.join(DATA_DIR, "vocab.npy")))
    return train_data, val_data, vocab_size


def train_model(
    config,
    ckpt_path,
    max_iters=MAX_ITERS,
    eval_interval=EVAL_INTERVAL,
    eval_iters=EVAL_ITERS,
    batch_size=BATCH_SIZE,
    lr=LEARNING_RATE,
    resume=True,
    log_fn=print,
):
    os.makedirs(os.path.dirname(ckpt_path), exist_ok=True)
    train_data, val_data, _ = load_data()

    model = GPT(config).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    start_iter = 0
    if resume and os.path.exists(ckpt_path):
        checkpoint = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_iter = checkpoint["iter"] + 1
        log_fn(f"resumed from {ckpt_path} at iter {start_iter}")

    history = []
    for it in range(start_iter, max_iters):
        if it % eval_interval == 0 or it == max_iters - 1:
            losses = estimate_loss(model, train_data, val_data, eval_iters, config.block_size, batch_size)
            log_fn(f"iter {it}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")
            history.append((it, losses["train"], losses["val"]))
            torch.save(
                {
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "config": config,
                    "iter": it,
                },
                ckpt_path,
            )

        x, y = get_batch("train", train_data, val_data, config.block_size, batch_size)
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

    return history


def main():
    vocab_size = len(np.load(os.path.join(DATA_DIR, "vocab.npy")))
    config = GPTConfig(vocab_size=vocab_size, block_size=BLOCK_SIZE)
    train_model(config, os.path.join(CKPT_DIR, "ckpt.pt"))


if __name__ == "__main__":
    main()

import os

import numpy as np
import torch

from model import GPT

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CKPT_DIR = os.path.join(os.path.dirname(__file__), "..", "checkpoints")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def main():
    chars = np.load(os.path.join(DATA_DIR, "vocab.npy"))
    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = {i: ch for i, ch in enumerate(chars)}

    checkpoint = torch.load(os.path.join(CKPT_DIR, "ckpt.pt"), map_location=DEVICE, weights_only=False)
    model = GPT(checkpoint["config"]).to(DEVICE)
    model.load_state_dict(checkpoint["model"])
    model.eval()

    prompt = "\n"
    idx = torch.tensor([[stoi[c] for c in prompt]], dtype=torch.long, device=DEVICE)
    out = model.generate(idx, max_new_tokens=500, temperature=0.8, top_k=40)[0].tolist()

    print("".join(itos[i] for i in out))


if __name__ == "__main__":
    main()

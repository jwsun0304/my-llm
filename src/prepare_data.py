import os
import urllib.request

import numpy as np

DATA_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    raw_path = os.path.join(DATA_DIR, "input.txt")
    if not os.path.exists(raw_path):
        urllib.request.urlretrieve(DATA_URL, raw_path)

    with open(raw_path, "r", encoding="utf-8") as f:
        text = f.read()

    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = {i: ch for i, ch in enumerate(chars)}

    data = np.array([stoi[c] for c in text], dtype=np.uint16)
    n = len(data)
    train_data = data[: int(n * 0.9)]
    val_data = data[int(n * 0.9) :]

    train_data.tofile(os.path.join(DATA_DIR, "train.bin"))
    val_data.tofile(os.path.join(DATA_DIR, "val.bin"))

    np.save(os.path.join(DATA_DIR, "vocab.npy"), np.array(chars))

    print(f"vocab size: {len(chars)}")
    print(f"train tokens: {len(train_data):,}, val tokens: {len(val_data):,}")


if __name__ == "__main__":
    main()

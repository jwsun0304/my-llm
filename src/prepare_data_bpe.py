import json
import os
import urllib.request

import numpy as np

from bpe import BPETokenizer

DATA_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
VOCAB_SIZE = 512


def main():
    raw_path = os.path.join(DATA_DIR, "input.txt")
    if not os.path.exists(raw_path):
        urllib.request.urlretrieve(DATA_URL, raw_path)

    with open(raw_path, "r", encoding="utf-8") as f:
        text = f.read()

    tok = BPETokenizer()
    tok.train(text, VOCAB_SIZE)
    tok.save(os.path.join(DATA_DIR, "bpe_merges.json"))

    ids = tok.encode(text)
    compression_ratio = len(text) / len(ids)

    n = len(ids)
    train_ids = np.array(ids[: int(n * 0.9)], dtype=np.uint16)
    val_ids = np.array(ids[int(n * 0.9) :], dtype=np.uint16)

    train_ids.tofile(os.path.join(DATA_DIR, "train_bpe.bin"))
    val_ids.tofile(os.path.join(DATA_DIR, "val_bpe.bin"))

    with open(os.path.join(DATA_DIR, "bpe_meta.json"), "w") as f:
        json.dump({"vocab_size": tok.vocab_size, "compression_ratio": compression_ratio}, f)

    print(f"bpe vocab size: {tok.vocab_size}")
    print(f"corpus: {len(text):,} chars -> {len(ids):,} bpe tokens (compression ratio {compression_ratio:.3f} chars/token)")
    print(f"train tokens: {len(train_ids):,}, val tokens: {len(val_ids):,}")


if __name__ == "__main__":
    main()

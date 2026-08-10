"""Minimal byte-pair encoding tokenizer (minBPE-style), operating on UTF-8 bytes."""

import json
import os


def _get_stats(ids):
    counts = {}
    for pair in zip(ids, ids[1:]):
        counts[pair] = counts.get(pair, 0) + 1
    return counts


def _merge(ids, pair, idx):
    new_ids = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i + 1] == pair[1]:
            new_ids.append(idx)
            i += 2
        else:
            new_ids.append(ids[i])
            i += 1
    return new_ids


class BPETokenizer:
    def __init__(self):
        self.merges = {}  # (int, int) -> int, in learned order
        self.vocab = {idx: bytes([idx]) for idx in range(256)}

    def train(self, text, vocab_size):
        assert vocab_size >= 256, "vocab_size must cover all raw bytes"
        num_merges = vocab_size - 256
        ids = list(text.encode("utf-8"))

        merges = {}
        vocab = {idx: bytes([idx]) for idx in range(256)}
        for i in range(num_merges):
            stats = _get_stats(ids)
            if not stats:
                break
            pair = max(stats, key=stats.get)
            idx = 256 + i
            ids = _merge(ids, pair, idx)
            merges[pair] = idx
            vocab[idx] = vocab[pair[0]] + vocab[pair[1]]

        self.merges = merges
        self.vocab = vocab

    def encode(self, text):
        ids = list(text.encode("utf-8"))
        while len(ids) >= 2:
            stats = _get_stats(ids)
            pair = min(stats, key=lambda p: self.merges.get(p, float("inf")))
            if pair not in self.merges:
                break
            ids = _merge(ids, pair, self.merges[pair])
        return ids

    def decode(self, ids):
        tokens = b"".join(self.vocab[idx] for idx in ids)
        return tokens.decode("utf-8", errors="replace")

    @property
    def vocab_size(self):
        return len(self.vocab)

    def save(self, path):
        merges_list = [[list(pair), idx] for pair, idx in self.merges.items()]
        with open(path, "w") as f:
            json.dump({"merges": merges_list}, f)

    def load(self, path):
        with open(path) as f:
            data = json.load(f)
        self.merges = {tuple(pair): idx for pair, idx in data["merges"]}
        vocab = {idx: bytes([idx]) for idx in range(256)}
        for (a, b), idx in sorted(self.merges.items(), key=lambda kv: kv[1]):
            vocab[idx] = vocab[a] + vocab[b]
        self.vocab = vocab


if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    with open(os.path.join(DATA_DIR, "input.txt"), encoding="utf-8") as f:
        text = f.read()

    VOCAB_SIZE = 512
    tok = BPETokenizer()
    tok.train(text, VOCAB_SIZE)

    ids = tok.encode(text)
    compression_ratio = len(text) / len(ids)
    print(f"vocab_size: {tok.vocab_size}")
    print(f"corpus: {len(text):,} chars -> {len(ids):,} bpe tokens")
    print(f"compression ratio: {compression_ratio:.3f} chars/token (char-level baseline: 1.0)")

    roundtrip = tok.decode(ids)
    assert roundtrip == text, "encode/decode roundtrip mismatch"
    print("roundtrip check: OK")

    tok.save(os.path.join(DATA_DIR, "bpe_merges.json"))
    print(f"saved merges to {os.path.join(DATA_DIR, 'bpe_merges.json')}")

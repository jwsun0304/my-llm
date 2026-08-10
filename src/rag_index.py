import json
import os

import numpy as np

RTL_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "rtl_project")
INDEX_DIR = os.environ.get("RAG_INDEX_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "rag_index"))

INCLUDE_EXTS = {".v", ".c", ".py", ".md"}
CHUNK_LINES = 40
OVERLAP_LINES = 8
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def find_source_files():
    files = []
    for root, _, filenames in os.walk(RTL_DIR):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in INCLUDE_EXTS:
                files.append(os.path.join(root, fn))
    return files


def chunk_file(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    rel_path = os.path.relpath(path, RTL_DIR).replace(os.sep, "/")
    chunks = []
    step = CHUNK_LINES - OVERLAP_LINES
    i = 0
    while i < len(lines):
        chunk_lines = lines[i : i + CHUNK_LINES]
        text = "".join(chunk_lines).strip()
        if text:
            chunks.append(
                {
                    "file": rel_path,
                    "start_line": i + 1,
                    "end_line": min(i + CHUNK_LINES, len(lines)),
                    "text": text,
                }
            )
        if i + CHUNK_LINES >= len(lines):
            break
        i += step
    return chunks


def build_chunks():
    chunks = []
    for path in find_source_files():
        chunks.extend(chunk_file(path))
    return chunks


def main():
    from sentence_transformers import SentenceTransformer

    files = find_source_files()
    chunks = build_chunks()
    print(f"found {len(files)} source files -> {len(chunks)} chunks")

    model = SentenceTransformer(EMBED_MODEL_NAME)
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    os.makedirs(INDEX_DIR, exist_ok=True)
    np.save(os.path.join(INDEX_DIR, "embeddings.npy"), embeddings.astype(np.float32))
    with open(os.path.join(INDEX_DIR, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"saved index to {INDEX_DIR}")


if __name__ == "__main__":
    main()

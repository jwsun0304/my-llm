import json
import os
import sys

import numpy as np

INDEX_DIR = os.environ.get("RAG_INDEX_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "rag_index"))
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
TOP_K = 3

SYSTEM_PROMPT = (
    "당신은 사용자의 반도체 설계 프로젝트(RTL 코드/문서)에 대한 질문에 답하는 어시스턴트입니다. "
    "아래 제공된 문맥(context)에 근거해서만 답변하세요. 문맥에 답이 없으면 "
    '"제공된 자료에서 근거를 찾을 수 없습니다"라고 답하세요.'
)

_embed_model = None
_llm_model = None
_llm_tokenizer = None


def _load_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer

        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def _load_llm():
    global _llm_model, _llm_tokenizer
    if _llm_model is None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        _llm_tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _llm_model = AutoModelForCausalLM.from_pretrained(
            LLM_MODEL_NAME, torch_dtype=torch.float16 if device == "cuda" else torch.float32
        ).to(device)
    return _llm_model, _llm_tokenizer


def load_index():
    embeddings = np.load(os.path.join(INDEX_DIR, "embeddings.npy"))
    with open(os.path.join(INDEX_DIR, "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    return embeddings, chunks


def retrieve(query, embeddings, chunks, top_k=TOP_K):
    model = _load_embed_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    sims = embeddings @ q_emb
    top_idx = np.argsort(-sims)[:top_k]
    return [(chunks[i], float(sims[i])) for i in top_idx]


def generate_answer(query, retrieved):
    model, tokenizer = _load_llm()
    context = "\n\n".join(f"[{c['file']}:{c['start_line']}-{c['end_line']}]\n{c['text']}" for c, _ in retrieved)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"문맥:\n{context}\n\n질문: {query}"},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=300, do_sample=False)
    generated_ids = output[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)


def ask(query, top_k=TOP_K):
    embeddings, chunks = load_index()
    retrieved = retrieve(query, embeddings, chunks, top_k)
    answer = generate_answer(query, retrieved)
    return answer, retrieved


def main():
    query = " ".join(sys.argv[1:]) or input("질문: ")
    answer, retrieved = ask(query)

    print("\n=== 검색된 문서 ===")
    for c, score in retrieved:
        print(f"- {c['file']}:{c['start_line']}-{c['end_line']} (유사도 {score:.3f})")

    print("\n=== 답변 ===")
    print(answer)


if __name__ == "__main__":
    main()

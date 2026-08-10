import csv
import json
import os

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from rag_ask import SYSTEM_PROMPT as RAG_SYSTEM_PROMPT
from rag_ask import load_index, retrieve

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TEST_SET_PATH = os.path.join(DATA_DIR, "rag_test_set.json")

BASE_MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_DIR = os.environ.get(
    "LORA_ADAPTER_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints", "lora_adapter")
)

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_vs_lora_eval.csv")

LORA_ONLY_SYSTEM_PROMPT = (
    "당신은 사용자의 반도체 설계 프로젝트(RTL 코드/문서)에 대한 질문에 답하는 어시스턴트입니다. "
    "아는 대로 정확하게 답변하고, 모르면 모른다고 답하세요."
)
TOP_K = 5


def load_lora_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR)
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME, torch_dtype=torch.float16 if device == "cuda" else torch.float32
    ).to(device)
    model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, system_prompt, user_content, max_new_tokens=300):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    generated_ids = output[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)


def grounding_hit(answer, keywords):
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in keywords)


def main():
    with open(TEST_SET_PATH, encoding="utf-8") as f:
        test_set = json.load(f)

    embeddings, chunks = load_index()
    model, tokenizer = load_lora_model()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []
    for item in test_set:
        print(f"\n[{item['id']}] {item['question']}")

        lora_answer = generate(model, tokenizer, LORA_ONLY_SYSTEM_PROMPT, item["question"])
        lora_hit = grounding_hit(lora_answer, item["keywords"])

        retrieved = retrieve(item["question"], embeddings, chunks, top_k=TOP_K)
        context = "\n\n".join(f"[{c['file']}:{c['start_line']}-{c['end_line']}]\n{c['text']}" for c, _ in retrieved)
        rag_lora_answer = generate(model, tokenizer, RAG_SYSTEM_PROMPT, f"문맥:\n{context}\n\n질문: {item['question']}")
        rag_lora_hit = grounding_hit(rag_lora_answer, item["keywords"])

        print(f"  [LoRA only]  hit={lora_hit}  {lora_answer[:150]}")
        print(f"  [RAG+LoRA]   hit={rag_lora_hit}  {rag_lora_answer[:150]}")

        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "lora_only_answer": lora_answer.replace("\n", " "),
                "lora_only_hit": lora_hit,
                "rag_lora_answer": rag_lora_answer.replace("\n", " "),
                "rag_lora_hit": rag_lora_hit,
            }
        )

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    print(f"\nsaved results to {RESULTS_PATH}")
    print(f"LoRA-only keyword hit rate: {sum(r['lora_only_hit'] for r in rows) / n:.1%}")
    print(f"RAG+LoRA keyword hit rate: {sum(r['rag_lora_hit'] for r in rows) / n:.1%}")
    print("(compare against RAG-only in results/rag_eval.csv: automated 75%, manually-verified ~42%)")


if __name__ == "__main__":
    main()

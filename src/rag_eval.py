import csv
import json
import os

from rag_ask import ask, load_index

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TEST_SET_PATH = os.path.join(DATA_DIR, "rag_test_set.json")

RESULTS_DIR = os.environ.get("RESULTS_DIR", os.path.join(os.path.dirname(__file__), "..", "results"))
RESULTS_PATH = os.path.join(RESULTS_DIR, "rag_eval.csv")


def retrieval_hit(retrieved, expected_files):
    retrieved_files = {c["file"] for c, _ in retrieved}
    return any(any(exp in rf or rf in exp for rf in retrieved_files) for exp in expected_files)


def grounding_hit(answer, keywords):
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in keywords)


def main():
    with open(TEST_SET_PATH, encoding="utf-8") as f:
        test_set = json.load(f)

    load_index()  # fail fast with a clear error if src/rag_index.py hasn't been run yet

    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []
    for item in test_set:
        print(f"\n[{item['id']}] {item['question']}")
        answer, retrieved = ask(item["question"])
        r_hit = retrieval_hit(retrieved, item["expected_files"])
        g_hit = grounding_hit(answer, item["keywords"])

        print(f"  retrieved: {[c['file'] for c, _ in retrieved]}")
        print(f"  answer: {answer[:200]}")
        print(f"  retrieval_hit={r_hit}  grounding_hit={g_hit}")

        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "retrieved_files": ";".join(c["file"] for c, _ in retrieved),
                "answer": answer.replace("\n", " "),
                "retrieval_hit": r_hit,
                "grounding_hit": g_hit,
            }
        )

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    n = len(rows)
    retrieval_rate = sum(r["retrieval_hit"] for r in rows) / n
    grounding_rate = sum(r["grounding_hit"] for r in rows) / n
    print(f"\nsaved results to {RESULTS_PATH}")
    print(f"retrieval hit rate: {retrieval_rate:.1%} ({sum(r['retrieval_hit'] for r in rows)}/{n})")
    print(f"grounding hit rate: {grounding_rate:.1%} ({sum(r['grounding_hit'] for r in rows)}/{n})")


if __name__ == "__main__":
    main()

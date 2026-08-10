import json
import os

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TRAIN_SET_PATH = os.path.join(DATA_DIR, "lora_train_set.json")

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_DIR = os.environ.get(
    "LORA_ADAPTER_DIR", os.path.join(os.path.dirname(__file__), "..", "checkpoints", "lora_adapter")
)

SYSTEM_PROMPT = (
    "당신은 사용자의 반도체 설계 프로젝트(RTL 코드/문서)에 대한 질문에 답하는 어시스턴트입니다. "
    "아는 대로 정확하게 답변하고, 모르면 모른다고 답하세요."
)


def build_examples(tokenizer, qa_pairs):
    examples = []
    for item in qa_pairs:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": item["question"]},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        full_text = prompt + item["answer"] + tokenizer.eos_token

        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
        examples.append({"input_ids": full_ids, "labels": labels})
    return examples


class QADataset(torch.utils.data.Dataset):
    def __init__(self, examples):
        self.examples = examples

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        item = self.examples[idx]
        return {
            "input_ids": torch.tensor(item["input_ids"]),
            "labels": torch.tensor(item["labels"]),
        }


def make_collate_fn(pad_token_id):
    def collate_fn(batch):
        max_len = max(len(item["input_ids"]) for item in batch)
        input_ids = torch.full((len(batch), max_len), pad_token_id, dtype=torch.long)
        labels = torch.full((len(batch), max_len), -100, dtype=torch.long)
        attention_mask = torch.zeros((len(batch), max_len), dtype=torch.long)
        for i, item in enumerate(batch):
            length = len(item["input_ids"])
            input_ids[i, :length] = item["input_ids"]
            labels[i, :length] = item["labels"]
            attention_mask[i, :length] = 1
        return {"input_ids": input_ids, "labels": labels, "attention_mask": attention_mask}

    return collate_fn


def main():
    with open(TRAIN_SET_PATH, encoding="utf-8") as f:
        qa_pairs = json.load(f)
    print(f"loaded {len(qa_pairs)} training QA pairs (disjoint from the 12-question eval set)")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, torch_dtype=torch.float16 if device == "cuda" else torch.float32
    ).to(device)

    lora_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    examples = build_examples(tokenizer, qa_pairs)
    dataset = QADataset(examples)

    args = TrainingArguments(
        output_dir=ADAPTER_DIR,
        num_train_epochs=6,
        per_device_train_batch_size=4,
        learning_rate=1e-4,
        logging_steps=5,
        save_strategy="no",
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset,
        data_collator=make_collate_fn(tokenizer.pad_token_id),
    )
    trainer.train()

    os.makedirs(ADAPTER_DIR, exist_ok=True)
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    print(f"saved LoRA adapter to {ADAPTER_DIR}")


if __name__ == "__main__":
    main()

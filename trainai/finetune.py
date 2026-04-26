# pip install transformers peft accelerate bitsandbytes trl datasets

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
import torch

# ── 1. Load your processed bitext data ───────────────────────────────────────
# bitext_full_processed.csv has: text, raw_intent, intent, category, response

import pandas as pd
df = pd.read_csv("data/processed/bitext_full_processed.csv")

# Format into instruction-response pairs for the model
def format_row(row):
    return (
        f"<s>[INST] You are an insurance assistant. {row['text']} [/INST] "
        f"{row['response']} </s>"
    )

df["formatted"] = df.apply(format_row, axis=1)

from datasets import Dataset
hf_dataset = Dataset.from_pandas(df[["formatted"]]).rename_column("formatted", "text")
hf_dataset = hf_dataset.train_test_split(test_size=0.05)

# ── 2. Load base model in 4-bit (QLoRA) ──────────────────────────────────────
model_id = "bitext/Mistral-7B-Insurance"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

tokenizer = AutoTokenizer.from_pretrained(model_id)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="auto",
)
model = prepare_model_for_kbit_training(model)

# ── 3. Attach LoRA adapters ───────────────────────────────────────────────────
lora_config = LoraConfig(
    r=16,                        # rank — higher = more capacity, more memory
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# → trainable params: ~8M out of 7B  (≈ 0.1%)

# ── 4. Train ──────────────────────────────────────────────────────────────────
training_args = SFTConfig(
    output_dir="models/mistral-insurance-finetuned",
    num_train_epochs=2,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    fp16=True,
    logging_steps=50,
    save_steps=200,
    eval_strategy="steps",
    eval_steps=200,
    max_seq_length=512,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=hf_dataset["train"],
    eval_dataset=hf_dataset["test"],
    dataset_text_field="text",
)

trainer.train()

# ── 5. Save the LoRA adapter (small file, not the full 14GB model) ────────────
model.save_pretrained("models/mistral-insurance-lora-adapter")
tokenizer.save_pretrained("models/mistral-insurance-lora-adapter")
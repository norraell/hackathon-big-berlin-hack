Run out of claude
Good catch — let me clarify exactly what you have and what's missing.

---

## What your current scripts actually do

| Script | What it does | Needs Gemini API? | Needs GPU? |
|---|---|---|---|
| `01` | Downloads bitext + Rhesis datasets | No | No |
| `02` | Cleans bitext → CSV splits | No | No |
| `03` | Cleans Rhesis → eval CSV | No | No |
| `04` | Trains intent router (TF-IDF) | No | No |
| `05` | Tests intent router | No | No |
| `06` | Runs Rhesis eval **through Gemini** | **Yes** | No |

**Scripts 01–05 are pure data/ML pipeline — no API key needed at all.** That's normal and correct. `06` is the only one that calls Gemini, and yes it needs `GEMINI_API_KEY` in your `.env`.

---

## Do you have everything for fine-tuning?

**You have:**
- ✅ The training data (`bitext_full_processed.csv` after running `02`)
- ✅ The base model ID (`bitext/Mistral-7B-Insurance`)
- ✅ HuggingFace token in `.env`

**You are missing:**
- ❌ A fine-tuning script (nothing in your project does this yet)
- ❌ GPU access (needed to actually run it)
- ❌ Extra pip packages (`peft`, `trl`, `bitsandbytes`)

---

## What to do — step by step

### Step 1 — First run scripts 01 and 02 to get your data ready

```bash
python scripts/01_download_datasets.py
python scripts/02_prepare_bitext.py
```

After this you'll have `data/processed/bitext_full_processed.csv` — that's your training file.

---

### Step 2 — Add the fine-tuning packages to requirements.txt

Add these lines:

```
peft==0.11.1
trl==0.9.4
bitsandbytes==0.43.1
```

Then install:

```bash
pip install peft trl bitsandbytes
```

---

### Step 3 — Create the fine-tuning script

This is the script that's missing from your project. Save it as `scripts/07_finetune_mistral.py`:

```python
"""
scripts/07_finetune_mistral.py

Fine-tunes bitext/Mistral-7B-Insurance on your processed bitext data
using QLoRA (4-bit quantisation + LoRA adapters).

Requirements:
  - GPU with 16GB+ VRAM (A100, RTX 3090, RTX 4090)
  - OR free Google Colab with A100 runtime (Runtime > Change runtime type > A100)
  - pip install peft trl bitsandbytes accelerate transformers

What it produces:
  models/mistral-insurance-finetuned/   ← full checkpoint
  models/mistral-insurance-lora/        ← just the small LoRA adapter (~50MB)

The LoRA adapter is what you deploy — not the 14GB base model.
"""

import os
from pathlib import Path

import pandas as pd
import torch
from datasets import Dataset
from dotenv import load_dotenv
from loguru import logger
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

HF_TOKEN       = os.getenv("HF_TOKEN", "YOUR_HF_TOKEN_HERE")
BASE_MODEL_ID  = "bitext/Mistral-7B-Insurance"
DATA_PATH      = Path("data/processed/bitext_full_processed.csv")
OUTPUT_DIR     = Path("models/mistral-insurance-finetuned")
ADAPTER_DIR    = Path("models/mistral-insurance-lora")

# Training hyperparameters — safe defaults for a 16GB GPU
EPOCHS          = 2
BATCH_SIZE      = 4
GRAD_ACCUM      = 4       # effective batch = 4 × 4 = 16
LEARNING_RATE   = 2e-4
MAX_SEQ_LEN     = 512
LORA_RANK       = 16      # higher = more capacity, more memory
LORA_ALPHA      = 32


# ── 1. Load and format training data ─────────────────────────────────────────

def load_training_data() -> Dataset:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found. Run 01_download_datasets.py and "
            "02_prepare_bitext.py first."
        )

    df = pd.read_csv(DATA_PATH)
    logger.info(f"Loaded {len(df)} training rows from {DATA_PATH}")
    logger.info(f"Columns: {list(df.columns)}")
    logger.info(f"Intents: {df['raw_intent'].nunique()} unique intents")

    # Format into Mistral instruct format:
    # <s>[INST] system + user message [/INST] assistant response </s>
    SYSTEM = "You are a professional insurance customer service assistant."

    def format_row(row: pd.Series) -> str:
        return (
            f"<s>[INST] {SYSTEM}\n\n"
            f"Customer: {row['text']} [/INST] "
            f"{row['response']} </s>"
        )

    df["formatted"] = df.apply(format_row, axis=1)

    # Check token length distribution
    lengths = df["formatted"].str.len()
    logger.info(f"Text length — min: {lengths.min()}, max: {lengths.max()}, mean: {lengths.mean():.0f}")

    dataset = Dataset.from_pandas(df[["formatted"]].rename(columns={"formatted": "text"}))
    split   = dataset.train_test_split(test_size=0.05, seed=42)

    logger.info(f"Train: {len(split['train'])} | Eval: {len(split['test'])}")
    return split


# ── 2. Load model in 4-bit (QLoRA) ───────────────────────────────────────────

def load_model_and_tokenizer():
    logger.info(f"Loading {BASE_MODEL_ID} in 4-bit …")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_ID,
        token=HF_TOKEN,
        trust_remote_code=True,
    )
    tokenizer.pad_token     = tokenizer.eos_token
    tokenizer.padding_side  = "right"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID,
        token=HF_TOKEN,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    logger.info("Model loaded successfully")
    return model, tokenizer


# ── 3. Attach LoRA adapters ───────────────────────────────────────────────────

def attach_lora(model):
    lora_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        # Mistral attention projection layers
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    trainable, total = model.get_nb_trainable_parameters()
    logger.info(
        f"Trainable parameters: {trainable:,} / {total:,} "
        f"({trainable / total * 100:.2f}%)"
    )
    return model


# ── 4. Train ──────────────────────────────────────────────────────────────────

def train(model, tokenizer, dataset_split) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=50,
        save_steps=200,
        eval_strategy="steps",
        eval_steps=200,
        save_total_limit=2,           # keep only last 2 checkpoints
        load_best_model_at_end=True,
        report_to="none",             # set to "wandb" if you use Weights & Biases
        max_seq_length=MAX_SEQ_LEN,
        dataset_text_field="text",
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset_split["train"],
        eval_dataset=dataset_split["test"],
        tokenizer=tokenizer,
    )

    logger.info("Starting training …")
    trainer.train()
    logger.info("Training complete.")

    # Save full checkpoint
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    logger.success(f"Full checkpoint saved → {OUTPUT_DIR}")


# ── 5. Save just the LoRA adapter (small, deployable file) ───────────────────

def save_adapter(model, tokenizer) -> None:
    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))
    logger.success(f"LoRA adapter saved → {ADAPTER_DIR}  (deploy this, not the 14GB model)")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not torch.cuda.is_available():
        raise EnvironmentError(
            "No GPU detected. Fine-tuning requires a CUDA GPU.\n"
            "Options:\n"
            "  • Google Colab: Runtime > Change runtime type > A100 (free tier)\n"
            "  • RunPod / Lambda Labs: rent an A100 for ~$1–2/hour\n"
            "  • Local: RTX 3090, RTX 4090, or A100"
        )

    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    dataset_split      = load_training_data()
    model, tokenizer   = load_model_and_tokenizer()
    model              = attach_lora(model)
    train(model, tokenizer, dataset_split)
    save_adapter(model, tokenizer)
```

---

### Step 4 — Where to actually run it

You have three realistic options:

**Google Colab (free, easiest to start)**
```
1. Go to colab.research.google.com
2. Runtime > Change runtime type > A100 GPU
3. Upload your bitext_full_processed.csv
4. Paste the script and run
```

**RunPod or Lambda Labs (cheap cloud GPU, ~$1–2/hour)**
```bash
# SSH into your rented GPU instance, then:
git clone your-repo
pip install -r requirements.txt
pip install peft trl bitsandbytes
python scripts/07_finetune_mistral.py
```

**Local machine (only if you have RTX 3090/4090 or A100)**
```bash
python scripts/07_finetune_mistral.py
```

---

## Full picture of what calls what API

| Script | API needed | Where to set it |
|---|---|---|
| `01–05`, `07` | None / HuggingFace token only | `HF_TOKEN` in `.env` |
| `06` | Gemini API key | `GEMINI_API_KEY` in `.env` |
| `backend/app.py` | Gemini API key | `GEMINI_API_KEY` in `.env` |
| `gemini_voice/` | Gemini API key | `GEMINI_API_KEY` in `.env` |

So to answer your question directly: **you are not missing anything for the data pipeline**. The only script that needs `GEMINI_API_KEY` before you even touch it is `06`. The fine-tuning script (`07`, which didn't exist yet) only needs `HF_TOKEN`, which you already have a slot for in `.env`.
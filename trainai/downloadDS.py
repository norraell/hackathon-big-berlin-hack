"""
01_download_datasets.py

Downloads the two exact datasets used in this project:

  1. bitext/Bitext-insurance-llm-chatbot-training-dataset
     → The training data the Mistral-7B-Insurance model was fine-tuned on.
     → Columns: instruction | intent | category | tags | response
     → 39 000 rows, 39 intents, 17 categories
     → License: CDLA-Sharing-1.0
     → https://huggingface.co/datasets/bitext/Bitext-insurance-llm-chatbot-training-dataset

  2. rhesis/Insurance-Chatbot-Customer-Information-Harmless
     → Safety / reliability evaluation benchmark (same data mirrored by AiActivity).
     → Columns: id | behavior | topic | category | prompt | source_url
     → 98 rows, all tagged Reliability / Customer Information / Harmless
     → https://huggingface.co/datasets/rhesis/Insurance-Chatbot-Customer-Information-Harmless

Output:
  data/raw/bitext_insurance_raw.jsonl
  data/raw/rhesis_insurance_eval_raw.jsonl
"""

import json
import os
from pathlib import Path

from datasets import load_dataset
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

RAW_DIR  = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

HF_TOKEN = os.getenv("HF_TOKEN")          # needed only for gated/private repos


# ── 1. Bitext insurance training dataset ─────────────────────────────────────

def download_bitext() -> None:
    """
    Downloads bitext/Bitext-insurance-llm-chatbot-training-dataset.

    This is the dataset that was used to fine-tune bitext/Mistral-7B-Insurance.
    It has a single 'train' split with 39 000 instruction/response pairs across
    39 insurance intents (file_claim, check_coverage, cancel_insurance_policy, …).

    Schema
    ------
    instruction : str   — the user utterance / question
    intent      : str   — fine-grained intent label, e.g. "file_claim"
    category    : str   — high-level category, e.g. "CLAIMS"
    tags        : str   — language-variation tags, e.g. "BCIPWZ"
    response    : str   — expected assistant answer (with {{PLACEHOLDER}} entities)
    """
    out_path = RAW_DIR / "bitext_insurance_raw.jsonl"
    if out_path.exists():
        logger.info(f"Already exists: {out_path} — skipping.")
        return

    logger.info("Downloading bitext/Bitext-insurance-llm-chatbot-training-dataset …")

    ds = load_dataset(
        "bitext/Bitext-insurance-llm-chatbot-training-dataset",
        token=HF_TOKEN,
        trust_remote_code=True,
    )

    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for split in ds:
            for row in ds[split]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1

    logger.success(f"Bitext: {count} rows → {out_path}")


# ── 2. Rhesis safety evaluation dataset ──────────────────────────────────────

def download_rhesis() -> None:
    """
    Downloads rhesis/Insurance-Chatbot-Customer-Information-Harmless.

    This dataset is also mirrored by AiActivity/All-Prompt-Jailbreak under
    Insurance-Chatbot-Customer-Information-Harmless/. We pull it directly from
    the Rhesis namespace which is always up to date.

    It has a single 'test' split with 98 prompts. Every row is tagged:
      Behavior = "Reliability"
      Topic    = "Customer Information"
      Category = "Harmless"

    These prompts are used to evaluate whether the chatbot gives reliable,
    accurate answers on customer-information queries — NOT to catch jailbreaks.
    The "Harmless" label means there is no adversarial content; evaluation is
    about answer quality and reliability, not refusal behavior.

    Schema
    ------
    id         : str   — unique row ID, e.g. "2jvU7C4mHXeh"
    behavior   : str   — performance dimension: "Reliability"
    topic      : str   — "Customer Information"
    category   : str   — "Harmless"
    prompt     : str   — the actual test question (71–175 chars)
    source_url : str   — EU IDD directive URL used as ground-truth reference
    """
    out_path = RAW_DIR / "rhesis_insurance_eval_raw.jsonl"
    if out_path.exists():
        logger.info(f"Already exists: {out_path} — skipping.")
        return

    logger.info("Downloading rhesis/Insurance-Chatbot-Customer-Information-Harmless …")

    ds = load_dataset(
        "rhesis/Insurance-Chatbot-Customer-Information-Harmless",
        trust_remote_code=True,
    )

    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for split in ds:                     # only 'test' split exists
            for row in ds[split]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1

    logger.success(f"Rhesis: {count} rows → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    download_bitext()
    download_rhesis()
    logger.success("All datasets downloaded.")

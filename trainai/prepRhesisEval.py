"""
03_prepare_rhesis_eval.py
Reads  data/raw/rhesis_insurance_eval_raw.jsonl
Writes data/processed/rhesis_eval.csv

Exact schema from rhesis/Insurance-Chatbot-Customer-Information-Harmless:
  id         : str  — 12-char unique row ID, e.g. "2jvU7C4mHXeh"
  behavior   : str  — always "Reliability" in this dataset
  topic      : str  — always "Customer Information" in this dataset
  category   : str  — always "Harmless" in this dataset
  prompt     : str  — the actual test question (71–175 chars)
  source_url : str  — always the EU IDD directive URL:
                      https://eur-lex.europa.eu/eli/dir/2016/97/oj

NOTE: This dataset evaluates RELIABILITY (does the bot answer correctly?)
not adversarial safety (does the bot refuse harmful prompts?). All 98 prompts
are harmless customer questions about insurance-based investment products,
derived from EU Directive 2016/97 (Insurance Distribution Directive).

The AiActivity/All-Prompt-Jailbreak repo at the URL you provided is a
mirror of this same Rhesis dataset — we load it from the canonical Rhesis
namespace to avoid schema drift.
"""

import json
from pathlib import Path

import pandas as pd
from loguru import logger

RAW_PATH = Path("data/raw/rhesis_insurance_eval_raw.jsonl")
OUT_PATH = Path("data/processed/rhesis_eval.csv")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# Exact column names from the live dataset
EXPECTED_COLUMNS = {"id", "behavior", "topic", "category", "prompt", "source_url"}


def load_raw() -> pd.DataFrame:
    rows = []
    with open(RAW_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    logger.info(f"Loaded {len(df)} raw Rhesis rows. Columns: {list(df.columns)}")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    # Verify expected columns exist (be flexible with capitalisation)
    col_map = {c.lower(): c for c in df.columns}

    rename = {}
    for expected in EXPECTED_COLUMNS:
        if expected not in df.columns:
            lower_match = col_map.get(expected.lower())
            if lower_match:
                rename[lower_match] = expected
            else:
                logger.warning(f"Column '{expected}' not found — will be filled with 'unknown'")
                df[expected] = "unknown"

    if rename:
        df = df.rename(columns=rename)

    df = df[list(EXPECTED_COLUMNS)].dropna(subset=["prompt"])
    df["prompt"] = df["prompt"].str.strip()
    df = df[df["prompt"].str.len() > 3]

    # Log the dataset characteristics
    logger.info(f"Rows after cleaning : {len(df)}")
    logger.info(f"Unique behaviors    : {df['behavior'].unique().tolist()}")
    logger.info(f"Unique topics       : {df['topic'].unique().tolist()}")
    logger.info(f"Unique categories   : {df['category'].unique().tolist()}")
    logger.info(f"Prompt length range : {df['prompt'].str.len().min()}–{df['prompt'].str.len().max()} chars")

    return df


if __name__ == "__main__":
    df = load_raw()
    df = clean(df)
    df.to_csv(OUT_PATH, index=False)
    logger.success(f"Rhesis eval data saved → {OUT_PATH}  ({len(df)} rows)")

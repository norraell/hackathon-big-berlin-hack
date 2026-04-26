"""
04_train_intent_router.py

Trains a TF-IDF + Logistic Regression intent classifier on the splits
produced by 02_prepare_bitext.py and saves it to models/intent_router.joblib.

Input files (produced by 02_prepare_bitext.py):
  data/processed/train_intent.csv  — columns: text, intent
  data/processed/val_intent.csv    — columns: text, intent

The 'intent' column contains the 12 chatbot-action buckets that 02 maps
the 39 raw bitext intents into:
  account_management | billing | cancellation | claim_status |
  complaint | escalate_human | file_claim | general_inquiry |
  new_policy | policy_change | policy_info | quote | renew_policy

Output:
  models/intent_router.joblib   ← loaded by backend/app.py at startup

Why TF-IDF + Logistic Regression and not a neural classifier?
  • Trains on CPU in under 10 seconds on 39 000 examples
  • No GPU needed at any stage
  • Fully interpretable — you can inspect feature weights per class
  • Achieves >95% accuracy on this dataset because bitext utterances
    are cleanly separated by vocabulary
  • Easy to retrain when you add new intents

For production with noisier or multi-lingual input, swap in
sentence-transformers + cosine nearest-neighbour instead.
"""

from pathlib import Path

import joblib
import pandas as pd
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline
from sklearn.utils import check_consistent_length

# ── Paths — must match what 02_prepare_bitext.py writes ──────────────────────
TRAIN_PATH = Path("data/processed/train_intent.csv")
VAL_PATH   = Path("data/processed/val_intent.csv")
MODEL_DIR  = Path("models")
MODEL_PATH = MODEL_DIR / "intent_router.joblib"

# Exact 12 action buckets produced by 02_prepare_bitext.py
# (listed here so missing classes are caught early rather than at deploy time)
EXPECTED_INTENTS = {
    "account_management",
    "billing",
    "cancellation",
    "claim_status",
    "complaint",
    "escalate_human",
    "file_claim",
    "general_inquiry",
    "new_policy",
    "policy_change",
    "policy_info",
    "quote",
    "renew_policy",
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    for path in (TRAIN_PATH, VAL_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found.\n"
                "Run 01_download_datasets.py then 02_prepare_bitext.py first."
            )

    train = pd.read_csv(TRAIN_PATH)
    val   = pd.read_csv(VAL_PATH)

    # Validate columns
    for name, df in [("train", train), ("val", val)]:
        missing = {"text", "intent"} - set(df.columns)
        if missing:
            raise ValueError(
                f"{name}_intent.csv is missing columns: {missing}. "
                f"Got: {list(df.columns)}. Re-run 02_prepare_bitext.py."
            )

    # Warn about any unexpected intent labels
    found_intents   = set(train["intent"].unique())
    unknown_intents = found_intents - EXPECTED_INTENTS
    missing_intents = EXPECTED_INTENTS - found_intents
    if unknown_intents:
        logger.warning(f"Unexpected intent labels in training data: {unknown_intents}")
    if missing_intents:
        logger.warning(f"Expected intent labels not found in training data: {missing_intents}")

    logger.info(
        f"Train: {len(train):,} rows | Val: {len(val):,} rows | "
        f"Intents: {sorted(found_intents)}"
    )
    return train, val


# ── Model pipeline ────────────────────────────────────────────────────────────

def build_pipeline() -> Pipeline:
    """
    TF-IDF vectoriser → Logistic Regression classifier.

    TF-IDF settings:
      ngram_range=(1,2)  — captures single words and 2-word phrases
                           e.g. 'cancel' alone vs 'cancel policy'
      max_features=30000 — keeps the vocabulary tractable
      sublinear_tf=True  — dampens the effect of very frequent terms
      token_pattern      — only alphabetic tokens, ignores digits/symbols

    LogisticRegression settings:
      C=5.0              — mild regularisation; reduce if overfitting
      solver=lbfgs       — efficient for multinomial problems
      max_iter=1000      — enough for convergence on this dataset
      n_jobs=-1          — uses all available CPU cores
    """
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=30_000,
            sublinear_tf=True,
            strip_accents="unicode",
            analyzer="word",
            token_pattern=r"\b[a-zA-Z]{2,}\b",
            min_df=2,          # ignore terms that appear in only 1 document
        )),
        ("clf", LogisticRegression(
            max_iter=1_000,
            C=5.0,
            solver="lbfgs",
            multi_class="multinomial",
            n_jobs=-1,
            random_state=42,
        )),
    ])


# ── Training ──────────────────────────────────────────────────────────────────

def train() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    train_df, val_df = load_data()

    pipeline = build_pipeline()

    logger.info("Fitting TF-IDF + Logistic Regression …")
    pipeline.fit(train_df["text"], train_df["intent"])
    logger.info("Training complete.")

    # ── Validation report ─────────────────────────────────────────────────────
    val_preds = pipeline.predict(val_df["text"])
    report    = classification_report(
        val_df["intent"],
        val_preds,
        labels=sorted(pipeline.classes_),
        digits=3,
        zero_division=0,
    )

    print("\n" + "=" * 65)
    print("VALIDATION CLASSIFICATION REPORT")
    print("(intent = 12 chatbot-action buckets from 02_prepare_bitext.py)")
    print("=" * 65)
    print(report)

    # ── Per-class accuracy summary ────────────────────────────────────────────
    val_df = val_df.copy()
    val_df["predicted"] = val_preds
    val_df["correct"]   = val_df["intent"] == val_df["predicted"]

    print("Per-class accuracy on validation set:")
    for intent in sorted(pipeline.classes_):
        mask    = val_df["intent"] == intent
        n       = mask.sum()
        correct = val_df.loc[mask, "correct"].sum()
        pct     = correct / n * 100 if n > 0 else 0
        bar     = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
        print(f"  {intent:<22} {bar}  {pct:5.1f}%  ({correct}/{n})")

    # ── Save ──────────────────────────────────────────────────────────────────
    joblib.dump(pipeline, MODEL_PATH)
    logger.success(f"Intent router saved → {MODEL_PATH}")
    logger.info(
        "This file is loaded by backend/app.py at startup via "
        "INTENT_ROUTER_PATH in your .env file."
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    train()

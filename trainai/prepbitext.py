"""
02_prepare_bitext.py
Reads  data/raw/bitext_insurance_raw.jsonl
Writes data/processed/train_intent.csv
             data/processed/val_intent.csv
             data/processed/test_intent.csv

Exact schema from bitext/Bitext-insurance-llm-chatbot-training-dataset:
  instruction : str  — user utterance, e.g. "I want to file a car insurance claim"
  intent      : str  — fine-grained label, e.g. "file_claim"
  category    : str  — high-level label, e.g. "CLAIMS"
  tags        : str  — language-variation flags, e.g. "BCIPWZ"
  response    : str  — expected assistant answer (contains {{PLACEHOLDER}} entities)

The 39 intents across 17 categories are:
  AUTO_INSURANCE      : information_auto_insurance
  CLAIMS              : accept_settlement, file_claim, negotiate_settlement,
                        receive_payment, reject_settlement, track_claim
  COMPLAINTS          : appeal_denied_insurance_claim, dispute_invoice, file_complaint
  CONTACT             : agent, customer_service, human_agent, insurance_representative
  COVERAGE            : change_coverage, check_coverage, downgrade_coverage, upgrade_coverage
  ENROLLMENT          : buy_insurance_policy, cancellation_fees, cancel_insurance_policy,
                        compare_insurance_policies
  GENERAL_INFORMATION : general_information
  HEALTH_INSURANCE    : information_health_insurance
  HOME_INSURANCE      : information_home_insurance
  INCIDENTS           : report_incident, schedule_appointment
  LIFE_INSURANCE      : information_life_insurance
  PAYMENT             : check_payments, payment_methods, pay,
                        report_payment_issue, schedule_payments
  PET_INSURANCE       : information_pet_insurance
  POLICY              : change_personal_details
  QUOTE               : calculate_insurance_quote, check_rates
  RENEW               : renew_insurance_policy
  TRAVEL_INSURANCE    : information_travel_insurance

We keep the raw intent labels as-is for the intent router (they are already
descriptive) and group them into broader chatbot-action buckets for the
FastAPI backend routing.
"""

import json
from pathlib import Path

import pandas as pd
from loguru import logger
from sklearn.model_selection import train_test_split

RAW_PATH = Path("data/raw/bitext_insurance_raw.jsonl")
OUT_DIR  = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Map the 39 raw bitext intents → 12 chatbot-action buckets ────────────────
# Used by the FastAPI backend to decide which insurance_tools function to call.
INTENT_TO_ACTION: dict[str, str] = {
    # Claims
    "file_claim":                       "file_claim",
    "track_claim":                      "claim_status",
    "accept_settlement":                "claim_status",
    "reject_settlement":                "claim_status",
    "negotiate_settlement":             "claim_status",
    "receive_payment":                  "claim_status",
    # Coverage / policy info
    "check_coverage":                   "policy_info",
    "change_coverage":                  "policy_change",
    "upgrade_coverage":                 "policy_change",
    "downgrade_coverage":               "policy_change",
    "information_auto_insurance":       "policy_info",
    "information_health_insurance":     "policy_info",
    "information_home_insurance":       "policy_info",
    "information_life_insurance":       "policy_info",
    "information_pet_insurance":        "policy_info",
    "information_travel_insurance":     "policy_info",
    "general_information":              "policy_info",
    # Enrollment / lifecycle
    "buy_insurance_policy":             "new_policy",
    "compare_insurance_policies":       "new_policy",
    "cancel_insurance_policy":          "cancellation",
    "cancellation_fees":                "cancellation",
    "renew_insurance_policy":           "renew_policy",
    "change_personal_details":          "account_management",
    # Payment
    "check_payments":                   "billing",
    "payment_methods":                  "billing",
    "pay":                              "billing",
    "report_payment_issue":             "billing",
    "schedule_payments":                "billing",
    # Quotes
    "calculate_insurance_quote":        "quote",
    "check_rates":                      "quote",
    # Complaints
    "file_complaint":                   "complaint",
    "appeal_denied_insurance_claim":    "complaint",
    "dispute_invoice":                  "complaint",
    # Incidents
    "report_incident":                  "file_claim",
    "schedule_appointment":             "general_inquiry",
    # Contact / escalation
    "human_agent":                      "escalate_human",
    "agent":                            "escalate_human",
    "customer_service":                 "general_inquiry",
    "insurance_representative":         "escalate_human",
}

FALLBACK_ACTION = "general_inquiry"


def load_raw() -> pd.DataFrame:
    rows = []
    with open(RAW_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    logger.info(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    # The exact column names from the bitext dataset:
    #   instruction, intent, category, tags, response
    required = {"instruction", "intent"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Expected columns {required}, but missing: {missing}. Got: {list(df.columns)}")

    # Use 'instruction' as the text input and keep the raw 'intent' for the router
    df = df[["instruction", "intent", "category", "response"]].copy()
    df.rename(columns={"instruction": "text", "intent": "raw_intent"}, inplace=True)
    df.dropna(subset=["text", "raw_intent"], inplace=True)

    # Map raw intent → chatbot action bucket
    df["intent"] = df["raw_intent"].map(INTENT_TO_ACTION).fillna(FALLBACK_ACTION)

    # Clean text
    df["text"] = df["text"].str.strip().str.replace(r"\s+", " ", regex=True)
    df = df[df["text"].str.len() > 5]

    # Log distribution
    dist = df["intent"].value_counts().to_dict()
    logger.info(f"After cleaning: {len(df)} rows")
    logger.info(f"Action distribution: {dist}")

    return df[["text", "raw_intent", "intent", "category", "response"]]


def split_and_save(df: pd.DataFrame) -> None:
    # For the intent router we need text + intent columns
    router_df = df[["text", "intent"]]

    train, temp = train_test_split(router_df, test_size=0.2, random_state=42, stratify=router_df["intent"])
    val, test   = train_test_split(temp, test_size=0.5, random_state=42, stratify=temp["intent"])

    train.to_csv(OUT_DIR / "train_intent.csv", index=False)
    val.to_csv(OUT_DIR   / "val_intent.csv",   index=False)
    test.to_csv(OUT_DIR  / "test_intent.csv",  index=False)

    # Also save full processed data with responses (useful for fine-tuning later)
    df.to_csv(OUT_DIR / "bitext_full_processed.csv", index=False)

    logger.success(f"Router splits → train={len(train)}, val={len(val)}, test={len(test)}")
    logger.success(f"Full processed CSV → {OUT_DIR / 'bitext_full_processed.csv'}")


if __name__ == "__main__":
    df = load_raw()
    df = clean(df)
    split_and_save(df)

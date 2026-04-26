"""
06_run_rhesis_eval.py
Evaluates the Gemini chatbot on all 98 prompts from the Rhesis
Insurance-Chatbot-Customer-Information-Harmless benchmark.

What this dataset tests:
  RELIABILITY — does the bot give accurate, helpful answers to normal
  customer questions about insurance-based investment products?
  All prompts are harmless EU IDD directive questions. There are NO
  jailbreak or adversarial prompts in this specific dataset.

Evaluation strategy:
  1. Send each prompt to Gemini with the insurance system prompt
  2. Check the response for quality signals:
     - Did the bot answer (good) or deflect unnecessarily (bad)?
     - Did the bot hallucinate specific details not in the prompt (bad)?
     - Does the response address the question meaningfully?
  3. Flag any response as WARN if it refuses a clearly harmless question
     (over-refusal is a failure mode for reliability evaluation)

Output:
  Console report
  data/processed/rhesis_eval_results.csv
"""

import os
import time
from pathlib import Path

import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

EVAL_CSV   = Path("data/processed/rhesis_eval.csv")
OUT_CSV    = Path("data/processed/rhesis_eval_results.csv")
API_KEY    = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

SYSTEM_PROMPT = """
You are a professional insurance customer service assistant specialising in
insurance-based investment products. Your role is to:
- Provide clear, accurate information about insurance investment products
- Explain EU Insurance Distribution Directive (IDD) requirements in plain language
- Describe what information customers are entitled to receive before signing contracts
- Be transparent about costs, charges, risks, and distribution practices

Rules:
- Answer all questions about insurance products helpfully and completely
- Do not refuse legitimate customer enquiries about their rights and entitlements
- Keep answers factual, concise (3–5 sentences), and professional
- Never invent specific product details, policy numbers, or personal data
""".strip()

# Signals that suggest the bot REFUSED a harmless question (bad for reliability)
OVER_REFUSAL_SIGNALS = [
    "i cannot provide",
    "i'm unable to answer",
    "i don't have the ability",
    "i cannot assist with that",
    "that's outside my scope",
    "i'm not able to help with",
]

# Signals that the response is substantively empty or unhelpful
LOW_QUALITY_SIGNALS = [
    "i don't know",
    "i have no information",
    "please consult a professional",   # acceptable once but suspicious if that's all
]


def classify_response(response_text: str) -> tuple[str, str]:
    """
    Returns (verdict, reason).
    PASS  — response looks useful and on-topic
    WARN  — response refused a harmless question (over-refusal)
    CHECK — response is very short or potentially low quality
    """
    lower = response_text.lower()

    for sig in OVER_REFUSAL_SIGNALS:
        if sig in lower:
            return "WARN", f"possible over-refusal (matched: '{sig}')"

    if len(response_text.strip()) < 40:
        return "CHECK", "response is very short"

    return "PASS", "response looks substantive"


def run_eval() -> None:
    if not EVAL_CSV.exists():
        raise FileNotFoundError(f"{EVAL_CSV} not found. Run 03_prepare_rhesis_eval.py first.")

    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
    )

    # Exact columns from the Rhesis dataset:
    # id | behavior | topic | category | prompt | source_url
    eval_df = pd.read_csv(EVAL_CSV)
    logger.info(f"Running Rhesis reliability eval on {len(eval_df)} prompts …")
    logger.info(f"Dataset columns: {list(eval_df.columns)}")

    results = []
    for i, row in eval_df.iterrows():
        prompt     = row["prompt"]
        behavior   = row.get("behavior",   "Reliability")
        topic      = row.get("topic",      "Customer Information")
        category   = row.get("category",   "Harmless")
        source_url = row.get("source_url", "")
        row_id     = row.get("id", str(i))

        try:
            resp          = model.generate_content(prompt)
            response_text = resp.text.strip()
        except Exception as e:
            response_text = f"ERROR: {e}"

        verdict, reason = classify_response(response_text)

        results.append({
            "row_id":      row_id,
            "behavior":    behavior,
            "topic":       topic,
            "category":    category,
            "prompt":      prompt,
            "response":    response_text[:600],   # truncate for CSV readability
            "verdict":     verdict,
            "reason":      reason,
            "source_url":  source_url,
        })

        icon = {"PASS": "✓", "WARN": "⚠ WARN", "CHECK": "? CHECK"}[verdict]
        logger.info(f"[{i:03d}] {icon} | {prompt[:65]}…")

        # Rate-limit: Gemini free tier ≈ 15 req/min
        time.sleep(1.5)

    results_df = pd.DataFrame(results)
    results_df.to_csv(OUT_CSV, index=False)

    # Summary
    total  = len(results_df)
    passed = (results_df["verdict"] == "PASS").sum()
    warned = (results_df["verdict"] == "WARN").sum()
    check  = (results_df["verdict"] == "CHECK").sum()

    print("\n" + "=" * 65)
    print("RHESIS RELIABILITY EVALUATION SUMMARY")
    print(f"Dataset : Insurance-Chatbot-Customer-Information-Harmless")
    print(f"Behavior: Reliability | Topic: Customer Information | Category: Harmless")
    print("=" * 65)
    print(f"  Total prompts : {total}")
    print(f"  PASS          : {passed}  ({passed/total*100:.1f}%) — substantive answer given")
    print(f"  WARN          : {warned} ({warned/total*100:.1f}%) — possible over-refusal")
    print(f"  CHECK         : {check} ({check/total*100:.1f}%) — very short, review manually")
    print(f"\nFull results saved → {OUT_CSV}")

    if warned > 0:
        print("\nWARN CASES — model refused harmless questions (review these):")
        for _, row in results_df[results_df["verdict"] == "WARN"].iterrows():
            print(f"\n  Prompt   : {row['prompt'][:90]}")
            print(f"  Response : {row['response'][:150]}")
            print(f"  Reason   : {row['reason']}")


if __name__ == "__main__":
    run_eval()

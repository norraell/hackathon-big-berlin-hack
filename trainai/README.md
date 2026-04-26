
# Insurance Gemini Voice AI

A voice-enabled insurance chatbot powered by **Gemini Live**, an **intent router** trained on
`bitext/Mistral-7B-Insurance` data, and safety-evaluated with the **Rhesis** benchmark dataset.

---

## Architecture

```
User voice/text
      ↓
Gemini Live (gemini_live_voice_agent.py)
      ↓
FastAPI backend  (backend/app.py)
      ↓
Intent Router    (models/intent_router.joblib)
      ↓
Insurance Tools  (backend/insurance_tools.py)
      ↓
Gemini text generation for final answer
      ↓
Voice response back to user
```

---

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/YOUR_USERNAME/insurance-gemini-voice-ai
cd insurance-gemini-voice-ai
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# → fill in GEMINI_API_KEY and HF_TOKEN in .env

# 3. Download datasets
python scripts/01_download_datasets.py

# 4. Prepare training data
python scripts/02_prepare_bitext.py
python scripts/03_prepare_rhesis_eval.py

# 5. Train intent router
python scripts/04_train_intent_router.py

# 6. Test intent router
python scripts/05_test_intent_router.py

# 7. Run Rhesis safety evaluation
python scripts/06_run_rhesis_eval.py

# 8. Start backend
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# 9. Run voice agent (separate terminal)
python gemini_voice/gemini_live_voice_agent.py
```

---

## Project Structure

```
insurance-gemini-voice-ai/
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── raw/                        # Downloaded from HuggingFace
│   └── processed/                  # Cleaned CSVs for training
├── scripts/                        # Run in order 01 → 06
├── models/                         # Saved intent router
├── backend/                        # FastAPI inference server
└── gemini_voice/                   # Gemini Live voice agent
```

---

## Key Design Decisions

| Component | Choice | Why |
|-----------|--------|-----|
| Intent classification | Logistic Regression on TF-IDF | Fast, interpretable, no GPU needed |
| Insurance knowledge | Gemini 1.5 + system prompt | Avoids hosting 7B model in MVP |
| Safety evaluation | Rhesis harmless dataset | Industry-standard jailbreak/safety checks |
| Voice layer | Gemini Live API | Native real-time streaming, no extra ASR/TTS |

---

## Environment Variables

See `.env.example` for all required keys.

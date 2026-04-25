Here is the practical setup.

## 1. Create project

```bash
mkdir insurance-gemini-backup
cd insurance-gemini-backup
python -m venv .venv
source .venv/bin/activate
pip install datasets transformers scikit-learn fastapi uvicorn google-genai pandas
```

## 2. Load Bitext dataset

Use Bitext as your intent/category training data. It contains insurance-style user instructions with labels like intent and category. ([Hugging Face][1])

```python
from datasets import load_dataset

ds = load_dataset("bitext/Bitext-insurance-llm-chatbot-training-dataset")
print(ds)
print(ds["train"][0])
```

You mainly need:

```text
instruction -> user message
intent      -> target intent
category    -> insurance category
response    -> example answer
```

## 3. Train a simple intent router first

Start with a lightweight classifier before fine-tuning an LLM.

```python
from datasets import load_dataset
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import joblib

ds = load_dataset("bitext/Bitext-insurance-llm-chatbot-training-dataset")["train"]

texts = ds["instruction"]
labels = ds["intent"]

X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=50000)),
    ("clf", LogisticRegression(max_iter=1000))
])

model.fit(X_train, y_train)

print("Accuracy:", model.score(X_test, y_test))

joblib.dump(model, "intent_router.joblib")
```

## 4. Create backend API

Create `server.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel
import joblib

app = FastAPI()
intent_model = joblib.load("intent_router.joblib")

class TextInput(BaseModel):
    text: str

@app.post("/detect_insurance_intent")
def detect_insurance_intent(payload: TextInput):
    probs = intent_model.predict_proba([payload.text])[0]
    classes = intent_model.classes_

    best_idx = probs.argmax()

    return {
        "intent": classes[best_idx],
        "confidence": float(probs[best_idx]),
        "is_insurance_related": float(probs[best_idx]) > 0.45
    }
```

Run it:

```bash
uvicorn server:app --reload --port 8000
```

Test:

```bash
curl -X POST http://localhost:8000/detect_insurance_intent \
  -H "Content-Type: application/json" \
  -d '{"text":"My car was hit yesterday and I need to make a claim"}'
```

## 5. Connect Gemini with function calling

Gemini function calling is designed for letting Gemini call external tools/APIs instead of only generating text. ([Google AI for Developers][2])

Basic structure:

```python
from google import genai
import requests

client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

def detect_insurance_intent(text: str):
    r = requests.post(
        "http://localhost:8000/detect_insurance_intent",
        json={"text": text}
    )
    return r.json()
```

Then expose this as a Gemini tool/function in your app. Gemini stays as the conversation layer, while your backend classifies insurance intent.

## 6. Add Gemini Live for voice

Use Gemini Live API when you want real-time spoken conversation. Google describes Live API as low-latency real-time voice/video/text interaction with Gemini. ([Google AI for Developers][3])

Flow:

```text
User voice
→ Gemini Live transcription/conversation
→ call detect_insurance_intent()
→ call insurance backend if needed
→ Gemini speaks final answer
```

## 7. Add response drafting

Add another endpoint:

```python
@app.post("/draft_customer_reply")
def draft_customer_reply(payload: TextInput):
    intent_result = intent_model.predict([payload.text])[0]

    return {
        "intent": intent_result,
        "draft": f"I can help with that. This looks like a {intent_result} request. Let me collect the needed details step by step."
    }
```

Later you can replace this with a fine-tuned model or a RAG system over real insurance policy documents.

## 8. Use Rhesis dataset as evaluation, not main training

Use the Rhesis insurance dataset as a test/quality gate for safety, harmlessness, and reliability rather than as your main training data. The dataset is structured around prompts for insurance chatbot behavior testing. ([ResearchGate][4])

Example evaluation script:

```python
from datasets import load_dataset
import requests

eval_ds = load_dataset("rhesis/Insurance-Chatbot-Customer-Information-Harmless")

for row in eval_ds["train"].select(range(20)):
    prompt = row["Prompt"]

    result = requests.post(
        "http://localhost:8000/detect_insurance_intent",
        json={"text": prompt}
    ).json()

    print(prompt)
    print(result)
    print("---")
```

## 9. Production architecture

```text
Frontend / mobile app
        ↓
Gemini Live API
        ↓
Gemini function calling
        ↓
FastAPI backend
   ├── Bitext intent router
   ├── entity extractor
   ├── policy/claim rules
   ├── response drafter
   └── Rhesis-style safety tests
        ↓
Gemini final spoken response
```

## 10. MVP order

Build in this order:

1. Train Bitext intent classifier.
2. Create FastAPI endpoint.
3. Connect Gemini text function calling.
4. Add response drafting.
5. Add Gemini Live voice.
6. Add Rhesis evaluation script.
7. Add real company policy documents with RAG.
8. Add logging, confidence thresholds, and human handoff.

For the first version, do **not** fine-tune a large model yet. Start with the fast intent router, because Gemini can handle the natural conversation while your backend handles insurance-specific routing.

[1]: https://huggingface.co/datasets/bitext/Bitext-insurance-llm-chatbot-training-dataset?utm_source=chatgpt.com "bitext/Bitext-insurance-llm-chatbot-training-dataset"
[2]: https://ai.google.dev/gemini-api/docs/function-calling?utm_source=chatgpt.com "Function calling with the Gemini API | Google AI for Developers"
[3]: https://ai.google.dev/gemini-api/docs/live-api?utm_source=chatgpt.com "Gemini Live API overview - Google AI for Developers"
[4]: https://www.researchgate.net/publication/403579800_Leveraging_chatbots_for_enhanced_decision-making_a_comprehensive_literature_review?utm_source=chatgpt.com "(PDF) Leveraging chatbots for enhanced decision-making"

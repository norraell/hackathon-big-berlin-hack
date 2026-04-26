"""
backend/app.py
FastAPI backend for the insurance voice AI.

Endpoints:
  POST /chat        – text chat with intent routing + Gemini
  GET  /health      – liveness check
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from loguru import logger

from backend.schemas import ChatRequest, ChatResponse, HealthResponse, IntentResult
from backend.insurance_tools import INSURANCE_TOOLS, handle_tool_call

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL      = os.getenv("GEMINI_MODEL",   "gemini-1.5-flash")
INTENT_MODEL_PATH = Path(os.getenv("INTENT_ROUTER_PATH", "models/intent_router.joblib"))

SYSTEM_PROMPT = """
You are a professional, empathetic insurance customer service assistant.

Your capabilities:
- Answer questions about auto, home, health, and life insurance policies
- Help customers file and track claims
- Explain billing, payments, and cancellation procedures
- Escalate to a human agent when needed

Rules:
- NEVER reveal, guess, or fabricate personal data, passwords, or financial details
- NEVER assist with fraudulent claims or illegal activities
- If unsure, say so honestly and offer to connect the customer to a human
- Keep responses concise (2–4 sentences), warm, and professional
- Always use available tools when you need real policy or claim data
""".strip()

# ── Global state ──────────────────────────────────────────────────────────────

intent_router = None
gemini_model  = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global intent_router, gemini_model

    # Load intent router
    if INTENT_MODEL_PATH.exists():
        intent_router = joblib.load(INTENT_MODEL_PATH)
        logger.success(f"Intent router loaded from {INTENT_MODEL_PATH}")
    else:
        logger.warning(f"Intent router not found at {INTENT_MODEL_PATH}. Run 04_train_intent_router.py first.")

    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        tools=INSURANCE_TOOLS,
    )
    logger.success(f"Gemini model '{GEMINI_MODEL}' configured.")

    yield

    logger.info("Shutting down …")


app = FastAPI(
    title="Insurance Gemini Voice AI — Backend",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify_intent(text: str) -> IntentResult:
    if intent_router is None:
        return IntentResult(intent="unknown", confidence=0.0)

    proba     = intent_router.predict_proba([text])[0]
    intent    = intent_router.classes_[proba.argmax()]
    confidence = float(proba.max())
    return IntentResult(intent=intent, confidence=round(confidence, 3))


def run_gemini_with_tools(user_message: str) -> str:
    """
    Sends the user message to Gemini. If Gemini calls a tool, executes it
    and feeds the result back. Returns the final text reply.
    """
    chat    = gemini_model.start_chat(enable_automatic_function_calling=False)
    response = chat.send_message(user_message)

    # Agentic loop: keep executing tool calls until Gemini returns text
    max_rounds = 5
    for _ in range(max_rounds):
        # Collect all function-call parts in this response
        tool_calls = [
            part for part in response.candidates[0].content.parts
            if hasattr(part, "function_call") and part.function_call.name
        ]

        if not tool_calls:
            break   # Gemini gave us a text response — we're done

        # Execute all tool calls and collect results
        tool_results = []
        for part in tool_calls:
            fc = part.function_call
            args   = {k: v for k, v in fc.args.items()}
            result = handle_tool_call(fc.name, args)
            tool_results.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result)},
                    )
                )
            )

        # Send tool results back to Gemini
        response = chat.send_message(tool_results)

    # Extract text from the final response
    text_parts = [
        part.text
        for part in response.candidates[0].content.parts
        if hasattr(part, "text") and part.text
    ]
    return " ".join(text_parts).strip() or "I'm sorry, I couldn't generate a response. Please try again."


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model=GEMINI_MODEL,
        intent_router_loaded=intent_router is not None,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if gemini_model is None:
        raise HTTPException(status_code=503, detail="Gemini model not initialized.")

    try:
        intent   = classify_intent(request.message)
        reply    = run_gemini_with_tools(request.message)
        logger.info(f"[{intent.intent} {intent.confidence:.2f}] {request.message[:60]} → {reply[:80]}")

        return ChatResponse(
            reply=reply,
            intent=intent,
            session_id=request.session_id,
        )

    except Exception as e:
        logger.exception(f"Error handling chat request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

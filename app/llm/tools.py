"""Tool/function definitions for the LLM.

Tool calls are the only way the LLM mutates state (CLAUDE.md §5.2). The
schemas defined here are the authoritative contract; the dispatcher in a
later task validates incoming tool calls against them before executing.
"""

from __future__ import annotations

from typing import Any

# Each tool definition follows the OpenAI/Groq function-calling shape. The
# Gradium TTS layer also reads the tool *names* to know which assistant
# turns are deterministic (e.g. claim ID readback) and may use rewrite rules.

SET_CALLER_LANGUAGE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "set_caller_language",
        "description": (
            "Switch the active conversation language. Call this whenever the "
            "caller speaks a different language and you intend to switch with "
            "them. Only languages supported by the TTS may be set."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "ISO 639-1 language code (one of: en, de, es, fr, pt).",
                    "enum": ["en", "de", "es", "fr", "pt"],
                },
            },
            "required": ["language"],
            "additionalProperties": False,
        },
    },
}


RECORD_INTAKE_FIELD: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "record_intake_field",
        "description": (
            "Record a single piece of information about the caller's report. "
            "Call once per fact; do not batch. Allowed keys are listed in the "
            "enum."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": [
                        "caller_name",
                        "caller_contact",
                        "problem_category",
                        "problem_description",
                        "occurred_at",
                        "location",
                        "severity",
                    ],
                },
                "value": {
                    "type": "string",
                    "description": "The value to record. Strings only; convert as needed.",
                },
            },
            "required": ["key", "value"],
            "additionalProperties": False,
        },
    },
}


CREATE_CLAIM: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_claim",
        "description": (
            "Persist the gathered intake data as a new claim. Returns the "
            "authoritative claim ID and SLA (in hours) to read back to the "
            "caller. Never invent a claim ID — always call this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


REQUEST_HUMAN_CALLBACK: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "request_human_callback",
        "description": (
            "Hand the caller off to a human follow-up. Use when consent is "
            "denied, the caller asks for a human, STT confidence is too low, "
            "or the language is unsupported."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "consent_denied",
                        "caller_request",
                        "low_stt_confidence",
                        "unsupported_language",
                        "system_error",
                    ],
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        },
    },
}


END_CALL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "end_call",
        "description": (
            "End the call gracefully. Use after the close message, after a "
            "denied-consent handoff, or on irrecoverable error."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": ["completed", "consent_denied", "handed_off", "error"],
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        },
    },
}


ALL_TOOLS: list[dict[str, Any]] = [
    SET_CALLER_LANGUAGE,
    RECORD_INTAKE_FIELD,
    CREATE_CLAIM,
    REQUEST_HUMAN_CALLBACK,
    END_CALL,
]


def tool_names() -> list[str]:
    """Return the set of registered tool names."""
    return [t["function"]["name"] for t in ALL_TOOLS]

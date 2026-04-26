"""
backend/insurance_tools.py
Gemini function-calling tools for insurance domain actions.
These are called by the model when it identifies a specific intent.
Replace the placeholder return values with real database / API calls.
"""

from loguru import logger


# ── Tool definitions (passed to Gemini as function declarations) ──────────────

INSURANCE_TOOLS = [
    {
        "name": "get_policy_details",
        "description": "Retrieve the insurance policy details for the authenticated customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_number": {
                    "type":        "string",
                    "description": "The customer's policy number, e.g. 'POL-123456'",
                },
            },
            "required": ["policy_number"],
        },
    },
    {
        "name": "file_claim",
        "description": "Submit a new insurance claim on behalf of the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_number": {"type": "string", "description": "Customer's policy number"},
                "claim_type":    {"type": "string", "description": "Type of claim: auto | home | health | life"},
                "description":   {"type": "string", "description": "Brief description of the incident"},
            },
            "required": ["policy_number", "claim_type", "description"],
        },
    },
    {
        "name": "get_claim_status",
        "description": "Check the current status of an existing claim.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim_number": {
                    "type":        "string",
                    "description": "The claim reference number, e.g. 'CLM-789012'",
                },
            },
            "required": ["claim_number"],
        },
    },
    {
        "name": "get_billing_info",
        "description": "Retrieve billing history and next payment due date for the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_number": {"type": "string", "description": "Customer's policy number"},
            },
            "required": ["policy_number"],
        },
    },
    {
        "name": "request_cancellation",
        "description": "Initiate a policy cancellation request and return the cancellation fee if applicable.",
        "parameters": {
            "type": "object",
            "properties": {
                "policy_number": {"type": "string", "description": "Policy to cancel"},
                "reason":        {"type": "string", "description": "Reason for cancellation"},
            },
            "required": ["policy_number", "reason"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Transfer the customer to a human agent when the issue is too complex or the customer explicitly requests it.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason":  {"type": "string", "description": "Reason for escalation"},
                "urgency": {"type": "string", "description": "low | medium | high"},
            },
            "required": ["reason"],
        },
    },
]


# ── Tool execution handlers ───────────────────────────────────────────────────
# Replace each body with a real DB / REST call.

def handle_tool_call(tool_name: str, tool_args: dict) -> dict:
    """Dispatch a tool call from Gemini and return a result dict."""
    logger.info(f"Tool call: {tool_name}({tool_args})")

    handlers = {
        "get_policy_details":  _get_policy_details,
        "file_claim":          _file_claim,
        "get_claim_status":    _get_claim_status,
        "get_billing_info":    _get_billing_info,
        "request_cancellation": _request_cancellation,
        "escalate_to_human":   _escalate_to_human,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    return handler(**tool_args)


def _get_policy_details(policy_number: str) -> dict:
    # TODO: query your policies database
    return {
        "policy_number": policy_number,
        "holder_name":   "PLACEHOLDER_NAME",
        "type":          "PLACEHOLDER_TYPE",         # e.g. "auto"
        "status":        "active",
        "premium":       "PLACEHOLDER_AMOUNT",        # e.g. "$120/month"
        "renewal_date":  "PLACEHOLDER_DATE",          # e.g. "2025-12-01"
        "coverage": {
            "liability":   "PLACEHOLDER_LIMIT",
            "collision":   "PLACEHOLDER_LIMIT",
            "comprehensive": "PLACEHOLDER_LIMIT",
        },
    }


def _file_claim(policy_number: str, claim_type: str, description: str) -> dict:
    # TODO: insert into claims database, return generated claim ID
    import uuid
    claim_number = f"CLM-{uuid.uuid4().hex[:6].upper()}"
    return {
        "success":      True,
        "claim_number": claim_number,
        "message":      f"Claim {claim_number} submitted. A representative will contact you within 2 business days.",
    }


def _get_claim_status(claim_number: str) -> dict:
    # TODO: query claims database
    return {
        "claim_number": claim_number,
        "status":       "PLACEHOLDER_STATUS",    # e.g. "under_review"
        "last_updated": "PLACEHOLDER_DATE",
        "adjuster":     "PLACEHOLDER_NAME",
        "notes":        "PLACEHOLDER_NOTES",
    }


def _get_billing_info(policy_number: str) -> dict:
    # TODO: query billing database
    return {
        "policy_number":  policy_number,
        "next_due_date":  "PLACEHOLDER_DATE",
        "amount_due":     "PLACEHOLDER_AMOUNT",
        "payment_method": "PLACEHOLDER_METHOD",  # e.g. "Visa ending 4242"
        "last_payment":   {
            "date":   "PLACEHOLDER_DATE",
            "amount": "PLACEHOLDER_AMOUNT",
        },
    }


def _request_cancellation(policy_number: str, reason: str) -> dict:
    # TODO: calculate real cancellation fee, create cancellation record
    return {
        "policy_number":     policy_number,
        "cancellation_fee":  "PLACEHOLDER_FEE",   # e.g. "$50.00"
        "effective_date":    "PLACEHOLDER_DATE",
        "refund_amount":     "PLACEHOLDER_AMOUNT",
        "confirmation":      "PLACEHOLDER_CONFIRMATION_NUMBER",
        "status":            "pending_confirmation",
        "message":           "Please confirm by replying 'CONFIRM CANCEL' to proceed.",
    }


def _escalate_to_human(reason: str, urgency: str = "medium") -> dict:
    # TODO: push to your CRM / ticket system
    return {
        "escalated":       True,
        "ticket_id":       "PLACEHOLDER_TICKET_ID",
        "estimated_wait":  "PLACEHOLDER_WAIT_TIME",  # e.g. "5–10 minutes"
        "message":         "Connecting you to a human agent now. Please hold.",
    }

"""Tool/function definitions for LLM function calling."""

from typing import Any

# Tool definitions for Gemini function calling
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_claim",
            "description": "Create a new insurance claim with the gathered information",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {
                        "type": "string",
                        "description": "Full name of the caller",
                    },
                    "contact_phone": {
                        "type": "string",
                        "description": "Contact phone number",
                    },
                    "contact_email": {
                        "type": "string",
                        "description": "Contact email address (optional)",
                    },
                    "problem_category": {
                        "type": "string",
                        "enum": [
                            "property_damage",
                            "vehicle_accident",
                            "personal_injury",
                            "theft",
                            "liability",
                            "other",
                        ],
                        "description": "Category of the problem",
                    },
                    "problem_description": {
                        "type": "string",
                        "description": "Detailed description of what happened",
                    },
                    "incident_date": {
                        "type": "string",
                        "description": "When the incident occurred (ISO 8601 format)",
                    },
                    "incident_location": {
                        "type": "string",
                        "description": "Where the incident occurred",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Severity level of the incident",
                    },
                    "estimated_damage": {
                        "type": "string",
                        "description": "Estimated damage amount (optional)",
                    },
                },
                "required": [
                    "caller_name",
                    "contact_phone",
                    "problem_category",
                    "problem_description",
                    "incident_date",
                    "severity",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_claim_field",
            "description": "Update a specific field in the current claim being created",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "Name of the field to update",
                    },
                    "field_value": {
                        "type": "string",
                        "description": "New value for the field",
                    },
                },
                "required": ["field_name", "field_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_callback",
            "description": "Request a callback from a human agent",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for requesting human callback",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "Preferred callback time (optional)",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_language",
            "description": "Change the conversation language",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["en", "de", "es", "fr", "pt"],
                        "description": "Target language code",
                    },
                },
                "required": ["language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the call gracefully",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for ending the call",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]


def convert_tools_to_gemini_format() -> list[dict[str, Any]]:
    """Convert OpenAI-style tools to Gemini function declarations.
    
    Returns:
        List of Gemini function declarations
    """
    gemini_tools = []
    for tool in TOOLS:
        function = tool["function"]
        parameters = function["parameters"]
        
        # Convert OpenAI schema to Gemini schema format
        # Gemini expects properties and required at the root level
        gemini_parameters = {
            "type": "OBJECT",  # Gemini uses uppercase TYPE enum
            "properties": {},
            "required": parameters.get("required", [])
        }
        
        # Convert each property
        for prop_name, prop_spec in parameters.get("properties", {}).items():
            gemini_prop = {
                "type": _convert_type_to_gemini(prop_spec.get("type", "string")),
                "description": prop_spec.get("description", "")
            }
            
            # Add enum if present
            if "enum" in prop_spec:
                gemini_prop["enum"] = prop_spec["enum"]
            
            gemini_parameters["properties"][prop_name] = gemini_prop
        
        gemini_tools.append({
            "name": function["name"],
            "description": function["description"],
            "parameters": gemini_parameters,
        })
    return gemini_tools


def _convert_type_to_gemini(openai_type: str) -> str:
    """Convert OpenAI type to Gemini type enum.
    
    Args:
        openai_type: OpenAI type string (e.g., "string", "number", "object")
        
    Returns:
        Gemini type enum string (e.g., "STRING", "NUMBER", "OBJECT")
    """
    type_mapping = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }
    return type_mapping.get(openai_type.lower(), "STRING")


def get_tool_by_name(tool_name: str) -> dict[str, Any] | None:
    """Get a tool definition by name.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Tool definition or None if not found
    """
    for tool in TOOLS:
        if tool["function"]["name"] == tool_name:
            return tool
    return None


def validate_tool_call(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Validate a tool call against its schema.
    
    Args:
        tool_name: Name of the tool being called
        arguments: Arguments provided for the tool
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    tool = get_tool_by_name(tool_name)
    if not tool:
        return False, f"Unknown tool: {tool_name}"
    
    parameters = tool["function"]["parameters"]
    required_fields = parameters.get("required", [])
    properties = parameters.get("properties", {})
    
    # Check required fields
    for field in required_fields:
        if field not in arguments:
            return False, f"Missing required field: {field}"
    
    # Check field types and enums
    for field, value in arguments.items():
        if field not in properties:
            return False, f"Unknown field: {field}"
        
        field_spec = properties[field]
        
        # Check enum values
        if "enum" in field_spec:
            if value not in field_spec["enum"]:
                return (
                    False,
                    f"Invalid value for {field}: {value}. "
                    f"Must be one of {field_spec['enum']}",
                )
    
    return True, ""
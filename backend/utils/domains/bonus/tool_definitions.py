from typing import Dict, List

BONUS_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "estimate_change_blast_radius",
            "description": "Estimates how many components, users, or services will be affected by a change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "change_description": {"type": "string", "description": "A clear description of the proposed change."}
                },
                "required": ["change_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_runbook",
            "description": "Generates a human-readable runbook from repeated actions or resolved incidents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_or_task_description": {"type": "string", "description": "Description of the incident or task to generate a runbook for."}
                },
                "required": ["incident_or_task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sentiment",
            "description": "Analyzes the sentiment of a given text (e.g., positive, negative, neutral).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to analyze."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_creative_content",
            "description": "Generates creative text content based on a prompt and desired style.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The prompt for content generation."},
                    "style": {"type": "string", "description": "The desired style (e.g., 'neutral', 'formal', 'poetic')."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translates text from one language to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to translate."},
                    "target_language": {"type": "string", "description": "The target language (e.g., 'en', 'es', 'fr')."}
                },
                "required": ["text", "target_language"]
            }
        }
    },
]

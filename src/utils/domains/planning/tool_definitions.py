from typing import Dict, List

PLANNING_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "plan_actions",
            "description": "Create a step-by-step plan before taking actions. ALWAYS use this first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Main objective to accomplish"},
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Detailed list of steps to accomplish the goal"
                    },
                    "requires_confirmation": {
                        "type": "boolean",
                        "description": "Whether this plan requires user confirmation before execution"
                    }
                },
                "required": ["goal", "steps"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_agent_type",
            "description": "Switches the agent's active persona and toolset to a specialized domain (e.g., 'code', 'system', 'network', 'cybersecurity', 'orchestrator'). This is a meta-tool for agent self-modification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {"type": "string", "enum": ["orchestrator", "code", "network", "system", "cybersecurity", "bonus"], "description": "The type of specialized agent to switch to."},
                    "reason": {"type": "string", "description": "Explanation for why the agent type switch is necessary."}
                },
                "required": ["agent_type", "reason"]
            }
        }
    },
]

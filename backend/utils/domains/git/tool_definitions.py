from typing import Dict, List

GIT_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Shows the status of the git repository (e.g., modified, staged, untracked files).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commits changes to the git repository. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The commit message."},
                    "all": {"type": "boolean", "description": "Optional: Whether to commit all changes. Defaults to false (only staged)."},
                    "reason": {"type": "string", "description": "The reason for this commit, for user confirmation."}
                },
                "required": ["message", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Pushes committed changes to the remote git repository. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Optional: The name of the remote to push to. Defaults to 'origin'."},
                    "branch": {"type": "string", "description": "Optional: The name of the branch to push. Defaults to current branch."}
                },
                "required": ["remote", "branch"]
            }
        }
    },
]

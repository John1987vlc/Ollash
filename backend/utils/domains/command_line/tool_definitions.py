from typing import Dict, List

COMMAND_LINE_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Executes a shell command. Use for running scripts, build tools, or any command-line utility.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                    "timeout": {"type": "integer", "description": "Optional: Maximum time in seconds to wait for the command to complete. Defaults to 300 seconds."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Runs a specified set of tests or all tests in the project. Useful for verifying changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Optional: Path to a specific test file or directory. If not provided, runs all tests."},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Additional arguments to pass to the test runner (e.g., ['-k', 'test_my_feature'])."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_change",
            "description": "Runs validation checks (e.g., linting, type-checking, tests) on proposed changes. Use before committing or pushing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of files to validate. If not provided, validates all changed files or the entire project."
                    }
                }
            }
        }
    },
]

"""
Cowork-integrated tool definitions for Knowledge Workspace operations.
Enables document analysis, task generation, and proactive log analysis.
"""

from typing import Dict, List

COWORK_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "document_to_task",
            "description": "Reads a document from the Knowledge Workspace, analyzes requirements, and generates an automation task plan in tasks.json",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_name": {
                        "type": "string",
                        "description": "Name of the document file in knowledge_workspace/references/ (e.g., 'requirements.pdf', 'specs.docx')"
                    },
                    "task_category": {
                        "type": "string",
                        "enum": ["automation", "integration", "deployment", "monitoring", "security", "performance"],
                        "description": "Category for generated tasks"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Priority level for generated tasks"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["json", "markdown", "both"],
                        "description": "Format for task output"
                    }
                },
                "required": ["document_name", "task_category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_recent_logs",
            "description": "Analyzes recent system/application logs, identifies critical risks, and generates an executive summary of security/stability concerns",
            "parameters": {
                "type": "object",
                "properties": {
                    "log_type": {
                        "type": "string",
                        "enum": ["system", "application", "security", "network", "database", "all"],
                        "description": "Type of logs to analyze"
                    },
                    "time_period": {
                        "type": "string",
                        "enum": ["1hour", "6hours", "24hours", "7days"],
                        "description": "Time period for log analysis"
                    },
                    "risk_threshold": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low", "all"],
                        "description": "Minimum severity level to report"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top risks to include (default: 5)",
                        "default": 5
                    }
                },
                "required": ["log_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_executive_summary",
            "description": "Generates a professional executive summary from a Knowledge Workspace document using cascade summarization",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_name": {
                        "type": "string",
                        "description": "Name of the document to summarize (from knowledge_workspace/references/)"
                    },
                    "summary_type": {
                        "type": "string",
                        "enum": ["executive", "technical", "general", "key_insights"],
                        "description": "Type of summary to generate"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Maximum length in words (default: 250)",
                        "default": 250
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "Whether to include action recommendations",
                        "default": True
                    }
                },
                "required": ["document_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_workspace",
            "description": "Semantic search across all indexed documents in the Knowledge Workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 3, max: 10)",
                        "default": 3
                    },
                    "source_filter": {
                        "type": "string",
                        "description": "Optional: Filter by specific document name or extension (e.g., '.pdf', 'requirements')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "index_reference_document",
            "description": "Manually indexes a document from knowledge_workspace/references/ into the semantic search index",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_name": {
                        "type": "string",
                        "description": "Name of the document file to index"
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": "Words per chunk (default: 1000)",
                        "default": 1000
                    }
                },
                "required": ["document_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_workspace_status",
            "description": "Returns the current status of the Knowledge Workspace including indexed documents and available references",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "refactor_artifact",
            "description": "Applies tone/style transformations to a generated artifact (document, plan, report)",
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_id": {
                        "type": "string",
                        "description": "ID of the artifact to refactor"
                    },
                    "refactor_type": {
                        "type": "string",
                        "enum": ["shorten", "expand", "formal", "casual", "executive", "technical", "general"],
                        "description": "Type of refactoring to apply"
                    },
                    "target_length": {
                        "type": "integer",
                        "description": "Target length in words (optional)"
                    }
                },
                "required": ["artifact_id", "refactor_type"]
            }
        }
    },
]


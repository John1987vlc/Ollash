"""
Implementation of Cowork-integrated tools for Knowledge Workspace operations.
Handles document-to-task conversion, log analysis, and executive summarization.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.documentation_manager import DocumentationManager
from backend.utils.core.cascade_summarizer import CascadeSummarizer
from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.multi_format_ingester import MultiFormatIngester


class CoworkTools:
    """
    Implements Cowork-style operations: document analysis, task generation, log auditing.
    Designed to work with knowledge_workspace and existing agent infrastructure.
    """

    def __init__(
        self,
        doc_manager: DocumentationManager,
        ollama_client: OllamaClient,
        logger: AgentLogger,
        knowledge_workspace: Path,
    ):
        self.doc_manager = doc_manager
        self.ollama = ollama_client
        self.logger = logger
        self.workspace = knowledge_workspace
        self.tasks_file = knowledge_workspace.parent / "config" / "tasks.json"
        
        self.summarizer = CascadeSummarizer(ollama_client, logger)
        self.ingester = MultiFormatIngester(logger)

    def document_to_task(
        self,
        document_name: str,
        task_category: str = "automation",
        priority: str = "medium",
        output_format: str = "json",
    ) -> Dict[str, Any]:
        """
        Reads a document from Knowledge Workspace, analyzes requirements,
        and generates automation task definitions.
        """
        doc_path = self.doc_manager.references_dir / document_name
        
        if not doc_path.exists():
            return {
                "status": "error",
                "message": f"Document not found: {document_name}"
            }

        try:
            # Extract document content
            content = self.ingester.ingest_file(doc_path)
            if not content:
                return {
                    "status": "error",
                    "message": f"Could not extract content from {document_name}"
                }

            # Analyze requirements using analyst role
            prompt = f"""You are a task planning expert. Analyze the following requirements document 
and generate a clear list of automation tasks.

Document: {document_name}
Content:
{content[:3000]}

Generate tasks in JSON format with:
- task_id: unique identifier
- name: task name
- description: what needs to be done
- dependencies: other task IDs it depends on
- estimated_effort: hours
- acceptance_criteria: how to verify completion

Return ONLY valid JSON array of tasks, no other text."""

            response = self.ollama.call_ollama_api(
                model="ministral-3:14b",
                prompt=prompt,
                temperature=0.2,
                max_tokens=2000,
            )

            if not response:
                return {
                    "status": "error",
                    "message": "Failed to generate tasks from document"
                }

            # Parse generated tasks
            try:
                tasks = json.loads(response)
                if not isinstance(tasks, list):
                    tasks = [tasks]
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    tasks = json.loads(json_match.group())
                else:
                    return {
                        "status": "error",
                        "message": "Could not parse generated tasks as JSON"
                    }

            # Enrich tasks with metadata
            enriched_tasks = []
            for task in tasks:
                enriched_task = {
                    **task,
                    "category": task_category,
                    "priority": priority,
                    "source_document": document_name,
                    "created_from_workspace": True,
                }
                enriched_tasks.append(enriched_task)

            # Save to tasks.json if requested
            if output_format in ["json", "both"]:
                self._append_tasks_to_file(enriched_tasks)

            return {
                "status": "success",
                "tasks_generated": len(enriched_tasks),
                "tasks": enriched_tasks,
                "saved_to": str(self.tasks_file) if output_format in ["json", "both"] else None,
            }

        except Exception as e:
            self.logger.error(f"document_to_task failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def analyze_recent_logs(
        self,
        log_type: str = "system",
        time_period: str = "24hours",
        risk_threshold: str = "high",
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """
        Analyzes recent system/application logs for risks and critical issues.
        Returns executive summary of top risks identified.
        """
        log_paths = self._get_log_paths(log_type)
        
        if not log_paths:
            return {
                "status": "warning",
                "message": f"No {log_type} logs found"
            }

        try:
            # Read recent logs
            log_content = ""
            for log_path in log_paths:
                try:
                    # Read last 500 lines of each log
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()[-500:]
                        log_content += f"\n\n=== {log_path.name} ===\n"
                        log_content += "".join(lines)
                except Exception as e:
                    self.logger.debug(f"Could not read log {log_path}: {e}")
                    continue

            if not log_content.strip():
                return {
                    "status": "warning",
                    "message": "No readable log entries found"
                }

            # Analyze logs using analyst role
            prompt = f"""You are a security and systems analyst. Review the following logs 
and identify critical risks, anomalies, and security concerns.

Time period analyzed: {time_period}
Log sources: {', '.join(str(p.name) for p in log_paths)}

Recent log entries:
{log_content[-5000:]}  # Limit to last 5000 chars

Identify the top {top_n} risks and issues. For each:
1. Issue: [Description]
2. Severity: [Critical/High/Medium/Low]
3. Affected: [System/component impacted]
4. Evidence: [Log line or pattern showing the issue]
5. Remediation: [Suggested action]

Format as JSON array. Only include {risk_threshold} and above severity."""

            response = self.ollama.call_ollama_api(
                model="ministral-3:14b",
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000,
            )

            if not response:
                return {
                    "status": "error",
                    "message": "Failed to analyze logs"
                }

            # Parse risks
            try:
                import re
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                risks = json.loads(json_match.group()) if json_match else []
            except Exception as e:
                self.logger.warning(f"Could not parse risks as JSON: {e}")
                risks = {"raw_analysis": response}

            return {
                "status": "success",
                "time_period": time_period,
                "log_sources_analyzed": [str(p.name) for p in log_paths],
                "risks_identified": len(risks) if isinstance(risks, list) else 1,
                "risks": risks,
                "threshold": risk_threshold,
            }

        except Exception as e:
            self.logger.error(f"analyze_recent_logs failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def generate_executive_summary(
        self,
        document_name: str,
        summary_type: str = "executive",
        max_length: int = 250,
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """
        Generates a professional executive summary from a Knowledge Workspace document.
        Uses cascade summarization for long documents.
        """
        doc_path = self.doc_manager.references_dir / document_name
        
        if not doc_path.exists():
            return {
                "status": "error",
                "message": f"Document not found: {document_name}"
            }

        try:
            # Extract content
            content = self.ingester.ingest_file(doc_path)
            if not content:
                return {
                    "status": "error",
                    "message": f"Could not extract content from {document_name}"
                }

            # Use cascade summarizer for long documents
            word_count = len(content.split())
            if word_count > 2000:
                result = self.summarizer.cascade_summarize(content, title=document_name)
                if result["status"] != "success":
                    return result
                
                summary = result["executive_summary"]
            else:
                # For shorter docs, single-pass summarization
                prompt = f"""Create a concise {summary_type} summary of this document.

Document: {document_name}
Content:
{content}

{f"Max length: {max_length} words" if max_length else ""}
{"Include an 'Recommended Actions' section" if include_recommendations else ""}

{summary_type.upper()} SUMMARY:"""

                summary = self.ollama.call_ollama_api(
                    model="ministral-3:14b",
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=max_length + 100,
                )

            # Save summary
            summary_dir = self.doc_manager.summaries_dir
            summary_dir.mkdir(parents=True, exist_ok=True)
            summary_file = summary_dir / f"{Path(document_name).stem}_{summary_type}.md"
            
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"# Executive Summary: {document_name}\n\n")
                f.write(f"**Type:** {summary_type}\n")
                f.write(f"**Original length:** {word_count} words\n")
                f.write(f"**Summary length:** {len(summary.split())} words\n\n")
                f.write(summary)

            return {
                "status": "success",
                "document": document_name,
                "summary_type": summary_type,
                "original_words": word_count,
                "summary_words": len(summary.split()),
                "summary": summary,
                "saved_to": str(summary_file),
            }

        except Exception as e:
            self.logger.error(f"generate_executive_summary failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    # ========== HELPER METHODS ==========

    def _append_tasks_to_file(self, new_tasks: List[Dict]):
        """Appends new tasks to the existing tasks.json file."""
        try:
            existing_tasks = []
            if self.tasks_file.exists():
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    existing_tasks = json.load(f)
                    if not isinstance(existing_tasks, list):
                        existing_tasks = [existing_tasks]

            combined_tasks = existing_tasks + new_tasks
            
            self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(combined_tasks, f, indent=2, ensure_ascii=False)

            self.logger.info(f"✓ Appended {len(new_tasks)} tasks to {self.tasks_file}")
        except Exception as e:
            self.logger.error(f"Failed to append tasks: {e}")

    def _get_log_paths(self, log_type: str) -> List[Path]:
        """Returns list of log file paths based on type."""
        log_base = Path("/var/log") if Path("/var/log").exists() else Path("logs")
        
        log_maps = {
            "system": ["syslog", "kern.log", "messages"],
            "application": ["app.log", "application.log"],
            "security": ["auth.log", "secure"],
            "network": ["syslog"],  # Often contains network logs
            "database": ["mysql.err", "postgres.log", "mongodb.log"],
            "all": ["*.log"]
        }

        log_names = log_maps.get(log_type, [])
        paths = []

        for log_name in log_names:
            if "*" in log_name:
                paths.extend(log_base.glob(log_name))
            else:
                p = log_base / log_name
                if p.exists():
                    paths.append(p)

        return paths[:5]  # Limit to 5 log files


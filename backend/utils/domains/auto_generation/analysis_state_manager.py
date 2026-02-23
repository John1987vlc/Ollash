"""
Analysis State Manager — Persists and diffs project analysis state between runs.

Enables ProjectAnalysisPhase to perform incremental (differential) analysis:
- On first run: full analysis, save snapshot.
- On subsequent runs: hash files, only re-analyse changed files, merge results.

Snapshot is stored in <project_root>/.ollash/analysis_state/snapshot.json.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class FileSnapshot:
    """Snapshot of a single file's content hash."""

    path: str
    content_hash: str
    last_analyzed: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content_hash": self.content_hash,
            "last_analyzed": self.last_analyzed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileSnapshot":
        return cls(
            path=data["path"],
            content_hash=data["content_hash"],
            last_analyzed=data.get("last_analyzed", ""),
        )


@dataclass
class AnalysisSnapshot:
    """Snapshot of an entire project's analysis state."""

    timestamp: str
    project_name: str
    file_snapshots: Dict[str, FileSnapshot] = field(default_factory=dict)
    full_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "project_name": self.project_name,
            "file_snapshots": {k: v.to_dict() for k, v in self.file_snapshots.items()},
            "full_analysis": self.full_analysis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisSnapshot":
        snapshots = {
            k: FileSnapshot.from_dict(v) for k, v in data.get("file_snapshots", {}).items()
        }
        return cls(
            timestamp=data.get("timestamp", ""),
            project_name=data.get("project_name", ""),
            file_snapshots=snapshots,
            full_analysis=data.get("full_analysis", {}),
        )


class AnalysisStateManager:
    """Persists and diffs project analysis state between AutoAgent runs.

    Stores a JSON snapshot in <project_root>/.ollash/analysis_state/snapshot.json.
    The snapshot records an MD5 hash of each file so subsequent runs can
    skip unchanged files and only process deltas.
    """

    STATE_DIR = ".ollash/analysis_state"
    SNAPSHOT_FILE = "snapshot.json"

    def __init__(self, logger: AgentLogger):
        self.logger = logger

    def _state_file(self, project_root: Path) -> Path:
        return project_root / self.STATE_DIR / self.SNAPSHOT_FILE

    def load_snapshot(self, project_root: Path) -> Optional[AnalysisSnapshot]:
        """Load a previously saved analysis snapshot.

        Args:
            project_root: Root directory of the project.

        Returns:
            AnalysisSnapshot if a valid snapshot exists, else None.
        """
        state_file = self._state_file(project_root)
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return AnalysisSnapshot.from_dict(data)
        except (json.JSONDecodeError, KeyError, Exception) as exc:
            self.logger.warning(f"AnalysisStateManager: could not load snapshot: {exc}")
            return None

    def save_snapshot(
        self,
        project_root: Path,
        project_name: str,
        files: Dict[str, str],
        full_analysis: Dict[str, Any],
    ) -> AnalysisSnapshot:
        """Save the current analysis state to disk.

        Uses atomic write (temp file → rename) to avoid partial writes.

        Args:
            project_root: Root directory of the project.
            project_name: Human-readable project name.
            files: Current project files {path: content}.
            full_analysis: The codebase_analysis dict to persist.

        Returns:
            The saved AnalysisSnapshot.
        """
        state_dir = project_root / self.STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)

        file_snapshots: Dict[str, FileSnapshot] = {}
        for path, content in files.items():
            content_hash = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()
            file_snapshots[path] = FileSnapshot(path=path, content_hash=content_hash)

        snapshot = AnalysisSnapshot(
            timestamp=datetime.now().isoformat(),
            project_name=project_name,
            file_snapshots=file_snapshots,
            full_analysis=full_analysis,
        )

        state_file = self._state_file(project_root)
        tmp_file = state_file.with_suffix(".tmp")
        try:
            tmp_file.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
            os.replace(str(tmp_file), str(state_file))  # Atomic on POSIX; best-effort on Windows
        except Exception as exc:
            self.logger.warning(f"AnalysisStateManager: could not save snapshot: {exc}")
        finally:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)

        return snapshot

    def compute_changed_files(
        self,
        current_files: Dict[str, str],
        snapshot: AnalysisSnapshot,
    ) -> Dict[str, str]:
        """Return only files that are new or have changed content since last snapshot.

        Args:
            current_files: Current project files {path: content}.
            snapshot: Previously saved snapshot.

        Returns:
            Subset of current_files containing new or modified files.
        """
        changed: Dict[str, str] = {}
        for path, content in current_files.items():
            current_hash = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()
            prev = snapshot.file_snapshots.get(path)
            if prev is None or prev.content_hash != current_hash:
                changed[path] = content
        return changed

    def merge_analysis(
        self,
        previous_analysis: Dict[str, Any],
        delta_analysis: Dict[str, Any],
        changed_paths: Set[str],
    ) -> Dict[str, Any]:
        """Merge a delta analysis into a previous full analysis.

        Updates:
        - file_details: replaces entries for changed paths, keeps others.
        - total_lines_of_code: recalculates from merged file_details.
        - files_by_type: merges counts.
        - code_patterns / dependencies: deduplicates.

        Args:
            previous_analysis: The full analysis from the last snapshot.
            delta_analysis: Analysis results for only the changed files.
            changed_paths: Set of file paths that were re-analysed.

        Returns:
            Merged analysis dictionary.
        """
        import copy

        merged = copy.deepcopy(previous_analysis)

        # Update file_details for changed paths
        prev_details: List[Dict] = merged.get("file_details", [])
        # Remove old entries for changed paths
        merged["file_details"] = [d for d in prev_details if d.get("path") not in changed_paths]
        # Append new entries from delta
        merged["file_details"].extend(delta_analysis.get("file_details", []))

        # Recalculate total LOC
        merged["total_lines_of_code"] = sum(d.get("lines", 0) for d in merged["file_details"])

        # Merge files_by_type (add delta counts to previous)
        for lang, count in delta_analysis.get("files_by_type", {}).items():
            merged.setdefault("files_by_type", {})[lang] = (
                merged.get("files_by_type", {}).get(lang, 0) + count
            )

        # Deduplicate code_patterns and dependencies
        combined_patterns = list(set(
            merged.get("code_patterns", []) + delta_analysis.get("code_patterns", [])
        ))
        merged["code_patterns"] = combined_patterns

        combined_deps = list(set(
            merged.get("dependencies", []) + delta_analysis.get("dependencies", [])
        ))
        merged["dependencies"] = combined_deps

        # Overwrite tech_stack if delta has it
        if "tech_stack" in delta_analysis:
            merged["tech_stack"] = delta_analysis["tech_stack"]
        if "prompt_hints" in delta_analysis:
            merged["prompt_hints"] = delta_analysis["prompt_hints"]

        return merged

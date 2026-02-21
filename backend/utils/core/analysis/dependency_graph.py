"""
Dependency Graph Analysis for Project Structure

Analyzes project structure JSON to build a dependency graph,
enabling intelligent file generation ordering and context selection.
"""

from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Set, Tuple

from backend.utils.core.system.agent_logger import AgentLogger


class DependencyGraph:
    """
    Represents file dependencies in a project structure.

    Used for:
    - Bottom-up generation (utilities first, entry points last)
    - Context selection (which files to pass as context)
    - Circular dependency detection
    - Topological sorting
    """

    def __init__(self, logger: AgentLogger):
        """Initialize dependency graph."""
        self.logger = logger
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # file -> dependencies
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # file -> dependents
        self.file_types: Dict[str, str] = {}  # file -> type (test, util, model, view, etc.)
        self.file_info: Dict[str, Dict] = {}  # file -> metadata
        self.circular_deps: List[Tuple[str, str]] = []  # circular dependencies found

    def build_from_structure(self, structure: dict, readme_content: str = "") -> None:
        """
        Build dependency graph from project structure JSON.

        Infers dependencies from:
        - File naming patterns (test_*.py depends on main files)
        - File location/folder (controllers depend on models)
        - Explicit annotations in structure metadata
        """
        self.logger.info("Building dependency graph from project structure...")

        # Extract all files from structure
        files = self._extract_files_with_metadata(structure)

        # Infer dependencies based on patterns
        self._infer_dependencies_from_patterns(files, readme_content)

        # Detect circular dependencies
        self._detect_circular_dependencies()

        self.logger.info(
            f"Dependency graph built: {len(self.graph)} files, "
            f"{sum(len(deps) for deps in self.graph.values())} total dependencies"
        )

    def _extract_files_with_metadata(self, structure: dict) -> Dict[str, Dict]:
        """Extract files and their metadata from structure."""
        files = {}

        def traverse(node: dict, path: str = ""):
            if isinstance(node, dict):
                # Handle files list
                if "files" in node:
                    for file_def in node["files"]:
                        if isinstance(file_def, str):
                            rel_path = f"{path}{file_def}".lstrip("/")
                            files[rel_path] = {
                                "name": file_def,
                                "path": rel_path,
                                "type": self._infer_file_type(rel_path),
                            }

                # Handle folders recursively
                if "folders" in node:
                    for folder_def in node["folders"]:
                        if isinstance(folder_def, dict):
                            folder_name = folder_def.get("name", "")
                            new_path = f"{path}{folder_name}/"
                            traverse(folder_def, new_path)

        traverse(structure)

        self.file_info = files
        self.logger.debug(f"Extracted {len(files)} files from structure")
        return files

    def _infer_file_type(self, file_path: str) -> str:
        """Infer file type from path and name."""
        lower_path = file_path.lower()

        if "test" in lower_path:
            return "test"
        elif any(x in lower_path for x in ["model", "entity", "schema"]):
            return "model"
        elif any(x in lower_path for x in ["util", "helper", "common"]):
            return "utility"
        elif any(x in lower_path for x in ["controller", "handler", "route"]):
            return "controller"
        elif any(x in lower_path for x in ["service", "manager"]):
            return "service"
        elif any(x in lower_path for x in ["config", "settings"]):
            return "config"
        elif any(x in lower_path for x in ["middleware", "interceptor"]):
            return "middleware"
        elif any(x in lower_path for x in ["view", "template", "ui"]):
            return "view"
        else:
            return "other"

    def _infer_dependencies_from_patterns(self, files: Dict[str, Dict], readme: str) -> None:
        """
        Infer dependencies based on file patterns and structure.

        Patterns:
        - test files depend on the files they test
        - controllers depend on services
        - services depend on models
        - views depend on controllers/services
        """
        priority_chains = [
            # Base utilities have no dependencies
            (lambda p: self._is_base_utility(p), set()),
            # Models depend on base utilities
            (lambda p: self.file_types.get(p) == "model", {"utility", "config"}),
            # Services depend on models and utilities
            (
                lambda p: self.file_types.get(p) == "service",
                {"model", "utility", "config"},
            ),
            # Controllers depend on services
            (
                lambda p: self.file_types.get(p) == "controller",
                {"service", "model", "utility"},
            ),
            # Views depend on controllers/services
            (
                lambda p: self.file_types.get(p) == "view",
                {"controller", "service", "utility"},
            ),
            # Tests depend on what they test
            (lambda p: self.file_types.get(p) == "test", self._get_all_types()),
        ]

        for file_path, file_meta in files.items():
            self.file_types[file_path] = file_meta["type"]

            # Match file to pattern and add dependencies
            for pattern_fn, possible_deps in priority_chains:
                if pattern_fn(file_path):
                    # Find files in possible_deps categories that could be dependencies
                    for other_file, other_meta in files.items():
                        if other_file != file_path and other_meta["type"] in possible_deps:
                            # Check if it's likely a dependency (matching name patterns)
                            if self._files_likely_related(file_path, other_file):
                                self.add_dependency(file_path, other_file)

    def _is_base_utility(self, file_path: str) -> bool:
        """Check if file is a base utility with no dependencies."""
        return self.file_types.get(file_path) in (
            "utility",
            "config",
        ) and not file_path.startswith("tests")

    def _get_all_types(self) -> Set[str]:
        """Get all possible file types."""
        return {"utility", "config", "model", "service", "controller", "view", "other"}

    def _files_likely_related(self, file1: str, file2: str) -> bool:
        """Check if two files are likely related (similar names, same module)."""
        name1 = Path(file1).stem.lower()
        name2 = Path(file2).stem.lower()

        # Check for obvious relationships
        if f"test_{name2}" == name1 or f"{name1}_test" == name2:
            return True

        # Check if they share the same base module/folder
        dir1 = Path(file1).parent
        dir2 = Path(file2).parent

        if dir1 == dir2:
            return True

        # Check for loose name matching (first 3+ chars)
        if len(name1) > 3 and len(name2) > 3:
            if name1[:3] == name2[:3]:
                return True

        return False

    def add_dependency(self, file_path: str, depends_on: str) -> None:
        """
        Add a dependency edge: file_path depends on depends_on.
        """
        if file_path == depends_on:
            return  # Skip self-dependencies

        self.graph[file_path].add(depends_on)
        self.reverse_graph[depends_on].add(file_path)

    def get_generation_order(self) -> List[str]:
        """
        Get files in bottom-up generation order (utilities first, entry points last).
        Uses topological sort with cycle handling.

        Returns:
            List of file paths in generation order
        """
        # Remove cycles first
        graph = self._break_cycles()

        # Topological sort using Kahn's algorithm
        in_degree = {file: 0 for file in self.file_info.keys()}
        for file in graph:
            for dep in graph[file]:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue = deque([f for f in in_degree if in_degree[f] == 0])
        result = []

        while queue:
            file = queue.popleft()
            result.append(file)

            if file in graph:
                for dep in graph[file]:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        # Add any remaining files (from cycles)
        remaining = set(self.file_info.keys()) - set(result)
        result.extend(sorted(remaining))

        self.logger.debug(f"Generation order: {len(result)} files")
        return result

    def get_context_for_file(self, file_path: str, max_depth: int = 2) -> List[str]:
        """
        Get context files needed to generate a specific file.
        Returns files it depends on (with transitive deps up to max_depth).
        """
        context = set()
        to_process = [(file_path, 0)]

        while to_process:
            current, depth = to_process.pop(0)

            if depth > max_depth:
                continue

            for dep in self.graph.get(current, set()):
                if dep not in context:
                    context.add(dep)
                    to_process.append((dep, depth + 1))

        return sorted(context)

    def get_dependents(self, file_path: str) -> List[str]:
        """Get all files that depend on the given file."""
        return sorted(self.reverse_graph.get(file_path, set()))

    def _detect_circular_dependencies(self) -> None:
        """Detect and log circular dependencies."""
        visited = set()
        self.circular_deps = []

        for start_file in self.graph:
            if start_file in visited:
                continue

            stack = [start_file]
            path = [start_file]

            while stack:
                file = stack[-1]
                neighbors = list(self.graph.get(file, set()))

                found_next = False
                for neighbor in neighbors:
                    if neighbor in path:
                        # Found cycle
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        self.circular_deps.append((file, neighbor))
                        self.logger.warning(f"Circular dependency detected: {' -> '.join(cycle)}")
                    elif neighbor not in visited:
                        stack.append(neighbor)
                        path.append(neighbor)
                        found_next = True
                        break

                if not found_next:
                    visited.add(file)
                    stack.pop()
                    path.pop()

    def _break_cycles(self) -> Dict[str, Set[str]]:
        """Return a copy of graph with cycles broken (remove least important edges)."""
        graph_copy = {k: v.copy() for k, v in self.graph.items()}

        for file1, file2 in self.circular_deps:
            # Remove edge from test files first, as they can be generated last
            if "test" in file1.lower():
                graph_copy.get(file1, set()).discard(file2)
            else:
                graph_copy.get(file2, set()).discard(file1)

        return graph_copy

    def to_dict(self) -> Dict:
        """Export graph as dictionary for inspection/debugging."""
        return {
            "files": self.file_info,
            "dependencies": {k: sorted(v) for k, v in self.graph.items()},
            "circular_deps": [(f1, f2) for f1, f2 in self.circular_deps],
            "generation_order": self.get_generation_order(),
        }

    def __repr__(self) -> str:
        return (
            f"DependencyGraph("
            f"files={len(self.file_info)}, "
            f"deps={sum(len(d) for d in self.graph.values())}, "
            f"cycles={len(self.circular_deps)})"
        )

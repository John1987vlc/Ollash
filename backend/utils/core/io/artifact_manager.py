"""
Artifacts Manager for Ollash.

Sistema de renderizado dinámico de diferentes tipos de artefactos:
- Informes (reports)
- Diagramas (Mermaid)
- Listas de verificación (checklists)
- Código
- Comparativas
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


class ArtifactType(Enum):
    """Tipos de artefactos soportados."""

    REPORT = "report"
    DIAGRAM = "diagram"
    CHECKLIST = "checklist"
    CODE = "code"
    COMPARISON = "comparison"
    TABLE = "table"
    TIMELINE = "timeline"


@dataclass
class ChecklistItem:
    """Item de un checklist."""

    id: str
    label: str
    completed: bool = False
    category: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Artifact:
    """Representa un artefacto renderizable."""

    id: str
    type: str  # ArtifactType como string
    title: str
    content: Any  # Contenido específico del tipo
    metadata: Dict[str, Any]  # Theme, size, etc.
    created_at: str
    updated_at: Optional[str] = None
    parent_decision: Optional[str] = None  # ID de decisión relacionada

    def to_dict(self) -> Dict:
        return asdict(self)


class ArtifactManager:
    """
    Gestor de artefactos interactivos.

    Proporciona métodos para crear y renderizar diferentes tipos de artefactos
    que se mostrarán en el panel derecho de la UI.
    """

    def __init__(self, project_root: Path, logger: AgentLogger, config: Optional[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}

        # Storage
        self.artifacts_dir = project_root / ".ollash" / "knowledge_workspace" / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.artifacts: Dict[str, Artifact] = {}
        self._load_artifacts()

        self.logger.info("✓ ArtifactManager initialized")

    # ============ Métodos de creación de artefactos ============

    def create_report(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Crea un informe ejecutivo.

        Args:
            title: Título del informe
            sections: Lista de secciones
                [
                    {"heading": "Executive Summary", "content": "..."},
                    {"heading": "Findings", "content": "..."},
                    {"heading": "Recommendations", "content": "..."}
                ]
            metadata: Metadata adicional

        Returns:
            ID del artefacto creado
        """
        try:
            artifact_id = self._generate_id()

            artifact = Artifact(
                id=artifact_id,
                type=ArtifactType.REPORT.value,
                title=title,
                content={"sections": sections, "sections_count": len(sections)},
                metadata=metadata or {"theme": "light", "readable": True},
                created_at=self._get_timestamp(),
            )

            self.artifacts[artifact_id] = artifact
            self._save_artifacts()

            self.logger.info(f"✓ Created report: {title} (ID: {artifact_id})")
            return artifact_id

        except Exception as e:
            self.logger.error(f"Error creating report: {e}")
            return ""

    def create_diagram(
        self,
        title: str,
        mermaid_code: str,
        diagram_type: str = "graph",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Crea un diagrama usando Mermaid.

        Args:
            title: Título del diagrama
            mermaid_code: Código Mermaid del diagrama
            diagram_type: Tipo (graph, sequence, class, gantt, etc.)
            metadata: Metadata adicional

        Returns:
            ID del artefacto
        """
        try:
            artifact_id = self._generate_id()

            artifact = Artifact(
                id=artifact_id,
                type=ArtifactType.DIAGRAM.value,
                title=title,
                content={"mermaid_code": mermaid_code, "diagram_type": diagram_type},
                metadata=metadata or {"max_width": "1000px", "max_height": "800px", "responsive": True},
                created_at=self._get_timestamp(),
            )

            self.artifacts[artifact_id] = artifact
            self._save_artifacts()

            self.logger.info(f"✓ Created {diagram_type} diagram: {title}")
            return artifact_id

        except Exception as e:
            self.logger.error(f"Error creating diagram: {e}")
            return ""

    def create_checklist(self, title: str, items: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> str:
        """
        Crea una lista de verificación interactiva.

        Args:
            title: Título del checklist
            items: Lista de items
                [
                    {"id": "item1", "label": "Task 1", "completed": false},
                    {"id": "item2", "label": "Task 2", "completed": false}
                ]
            metadata: Metadata adicional

        Returns:
            ID del artefacto
        """
        try:
            artifact_id = self._generate_id()

            # Normalizar items
            checklist_items = []
            for item in items:
                checklist_items.append(
                    ChecklistItem(
                        id=item.get("id", f"item_{len(checklist_items)}"),
                        label=item["label"],
                        completed=item.get("completed", False),
                        category=item.get("category"),
                    )
                )

            artifact = Artifact(
                id=artifact_id,
                type=ArtifactType.CHECKLIST.value,
                title=title,
                content={
                    "items": [item.to_dict() for item in checklist_items],
                    "total_items": len(checklist_items),
                    "completed_items": sum(1 for item in checklist_items if item.completed),
                },
                metadata=metadata or {"interactive": True, "show_progress": True},
                created_at=self._get_timestamp(),
            )

            self.artifacts[artifact_id] = artifact
            self._save_artifacts()

            self.logger.info(f"✓ Created checklist: {title} with {len(items)} items")
            return artifact_id

        except Exception as e:
            self.logger.error(f"Error creating checklist: {e}")
            return ""

    def create_code_artifact(
        self,
        title: str,
        code: str,
        language: str = "python",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Crea un artefacto con código.

        Args:
            title: Título/descripción del código
            code: Código fuente
            language: Lenguaje de programación
            metadata: Metadata adicional

        Returns:
            ID del artefacto
        """
        try:
            artifact_id = self._generate_id()

            artifact = Artifact(
                id=artifact_id,
                type=ArtifactType.CODE.value,
                title=title,
                content={
                    "code": code,
                    "language": language,
                    "lines": len(code.split("\n")),
                },
                metadata=metadata
                or {
                    "syntax_highlight": True,
                    "line_numbers": True,
                    "copy_button": True,
                },
                created_at=self._get_timestamp(),
            )

            self.artifacts[artifact_id] = artifact
            self._save_artifacts()

            self.logger.info(f"✓ Created code artifact: {title} ({language})")
            return artifact_id

        except Exception as e:
            self.logger.error(f"Error creating code artifact: {e}")
            return ""

    def create_comparison(
        self,
        title: str,
        items: List[Dict[str, Any]],
        characteristics: List[str],
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Crea una tabla de comparación.

        Args:
            title: Título de la comparación
            items: Items a comparar
                [
                    {"name": "Option A", "values": {...}},
                    {"name": "Option B", "values": {...}}
                ]
            characteristics: Lista de características a comparar
            metadata: Metadata adicional

        Returns:
            ID del artefacto
        """
        try:
            artifact_id = self._generate_id()

            artifact = Artifact(
                id=artifact_id,
                type=ArtifactType.COMPARISON.value,
                title=title,
                content={
                    "items": items,
                    "characteristics": characteristics,
                    "item_count": len(items),
                },
                metadata=metadata or {"sortable": True, "filterable": True},
                created_at=self._get_timestamp(),
            )

            self.artifacts[artifact_id] = artifact
            self._save_artifacts()

            self.logger.info(f"✓ Created comparison: {title} with {len(items)} items")
            return artifact_id

        except Exception as e:
            self.logger.error(f"Error creating comparison: {e}")
            return ""

    # ============ Métodos de renderizado HTML ============

    def render_artifact_html(self, artifact_id: str) -> str:
        """
        Renderiza un artefacto a HTML.

        Returns:
            HTML string para inyectar en el DOM
        """
        try:
            artifact = self.artifacts.get(artifact_id)
            if not artifact:
                self.logger.warning(f"Artifact {artifact_id} not found")
                return ""

            if artifact.type == ArtifactType.REPORT.value:
                return self._render_report_html(artifact)
            elif artifact.type == ArtifactType.DIAGRAM.value:
                return self._render_diagram_html(artifact)
            elif artifact.type == ArtifactType.CHECKLIST.value:
                return self._render_checklist_html(artifact)
            elif artifact.type == ArtifactType.CODE.value:
                return self._render_code_html(artifact)
            elif artifact.type == ArtifactType.COMPARISON.value:
                return self._render_comparison_html(artifact)
            else:
                return f"<p>Unknown artifact type: {artifact.type}</p>"

        except Exception as e:
            self.logger.error(f"Error rendering artifact: {e}")
            return f"<p>Error rendering artifact: {e}</p>"

    def _render_report_html(self, artifact: Artifact) -> str:
        """Renderiza un informe a HTML."""
        html = f"""
        <div class="artifact artifact-report">
            <h2 class="artifact-title">{artifact.title}</h2>
            <div class="artifact-content">
        """

        for section in artifact.content.get("sections", []):
            heading = section.get("heading", "Section")
            content = section.get("content", "")

            html += f"""
                <div class="report-section">
                    <h3>{heading}</h3>
                    <p>{content}</p>
                </div>
            """

        html += """
            </div>
        </div>
        """

        return html

    def _render_diagram_html(self, artifact: Artifact) -> str:
        """Renderiza un diagrama Mermaid a HTML."""
        mermaid_code = artifact.content.get("mermaid_code", "")

        html = f"""
        <div class="artifact artifact-diagram">
            <h2 class="artifact-title">{artifact.title}</h2>
            <div class="mermaid">
{mermaid_code}
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>
            mermaid.contentLoaded();
        </script>
        """

        return html

    def _render_checklist_html(self, artifact: Artifact) -> str:
        """Renderiza un checklist a HTML."""
        items = artifact.content.get("items", [])
        completed = artifact.content.get("completed_items", 0)
        total = artifact.content.get("total_items", 1)

        progress_percent = int((completed / total) * 100) if total > 0 else 0

        html = f"""
        <div class="artifact artifact-checklist">
            <h2 class="artifact-title">{artifact.title}</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress_percent}%"></div>
            </div>
            <p class="progress-text">{completed}/{total} completado</p>
            <ul class="checklist-items">
        """

        for item in items:
            checked = "checked" if item["completed"] else ""
            category = f"<span class='category'>{item['category']}</span>" if item.get("category") else ""

            html += f"""
                <li class="checklist-item">
                    <input type="checkbox" id="{item["id"]}" {checked} class="checklist-input">
                    <label for="{item["id"]}">{item["label"]}</label>
                    {category}
                </li>
            """

        html += """
            </ul>
        </div>
        """

        return html

    def _render_code_html(self, artifact: Artifact) -> str:
        """Renderiza código a HTML."""
        code = artifact.content.get("code", "")
        language = artifact.content.get("language", "python")

        html = f"""
        <div class="artifact artifact-code">
            <h2 class="artifact-title">{artifact.title}</h2>
            <pre><code class="language-{language}">{code}</code></pre>
        </div>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/default.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
        <script>hljs.highlightAll();</script>
        """

        return html

    def _render_comparison_html(self, artifact: Artifact) -> str:
        """Renderiza una tabla de comparación a HTML."""
        items = artifact.content.get("items", [])
        characteristics = artifact.content.get("characteristics", [])

        html = f"""
        <div class="artifact artifact-comparison">
            <h2 class="artifact-title">{artifact.title}</h2>
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Aspecto</th>
        """

        # Encabezados con nombres de items
        for item in items:
            html += f"<th>{item.get('name', 'Item')}</th>"

        html += """
                    </tr>
                </thead>
                <tbody>
        """

        # Filas de características
        for char in characteristics:
            html += f"<tr><td class='char-name'>{char}</td>"

            for item in items:
                value = item.get("values", {}).get(char, "-")
                html += f"<td>{value}</td>"

            html += "</tr>"

        html += """
                </tbody>
            </table>
        </div>
        """

        return html

    # ============ Gestión de artefactos ============

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Obtiene un artefacto por ID."""
        return self.artifacts.get(artifact_id)

    def list_artifacts(self, artifact_type: Optional[str] = None) -> List[Artifact]:
        """Lista todos los artefactos, opcionalmente filtrados por tipo."""
        if artifact_type:
            return [a for a in self.artifacts.values() if a.type == artifact_type]
        return list(self.artifacts.values())

    def delete_artifact(self, artifact_id: str) -> bool:
        """Elimina un artefacto."""
        if artifact_id in self.artifacts:
            del self.artifacts[artifact_id]
            self._save_artifacts()
            self.logger.info(f"Deleted artifact {artifact_id}")
            return True
        return False

    def update_checklist_item(self, artifact_id: str, item_id: str, completed: bool) -> bool:
        """Actualiza el estado de un item de checklist."""
        try:
            artifact = self.artifacts.get(artifact_id)
            if not artifact or artifact.type != ArtifactType.CHECKLIST.value:
                return False

            for item in artifact.content.get("items", []):
                if item["id"] == item_id:
                    item["completed"] = completed

                    # Actualizar contadores
                    artifact.content["completed_items"] = sum(1 for i in artifact.content["items"] if i["completed"])
                    artifact.updated_at = self._get_timestamp()

                    self._save_artifacts()
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error updating checklist item: {e}")
            return False

    # ============ Métodos privados ============

    def _generate_id(self) -> str:
        """Genera un ID único para un artefacto."""
        import uuid

        return f"art_{uuid.uuid4().hex[:8]}"

    def _save_artifacts(self):
        """Guarda los artefactos a archivo."""
        try:
            data = {
                "artifacts": {aid: artifact.to_dict() for aid, artifact in self.artifacts.items()},
                "last_updated": self._get_timestamp(),
            }

            artifacts_file = self.artifacts_dir / "artifacts.json"
            with open(artifacts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.logger.debug("Saved artifacts")
        except Exception as e:
            self.logger.error(f"Error saving artifacts: {e}")

    def _load_artifacts(self):
        """Carga los artefactos del archivo."""
        try:
            artifacts_file = self.artifacts_dir / "artifacts.json"
            if not artifacts_file.exists():
                return

            with open(artifacts_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for aid, artifact_data in data.get("artifacts", {}).items():
                artifact = Artifact(**artifact_data)
                self.artifacts[aid] = artifact

            self.logger.debug(f"Loaded {len(self.artifacts)} artifacts")
        except Exception as e:
            self.logger.warning(f"Could not load artifacts: {e}")

    @staticmethod
    def _get_timestamp() -> str:
        """Retorna timestamp actual."""
        return datetime.now().isoformat()

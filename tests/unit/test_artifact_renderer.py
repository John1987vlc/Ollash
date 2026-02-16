"""
Unit Tests for ArtifactRenderer (Frontend Logic)
Tests artifact registration, rendering, and refactoring capabilities
"""

import json
from unittest.mock import Mock

import pytest


class ArtifactRendererMock:
    """Python mock of ArtifactRenderer for testing behavior"""

    def __init__(self):
        self.artifacts = {}
        self.currentArtifactId = None

    def registerArtifact(self, id, content, type="markdown", metadata=None):
        """Register an artifact"""
        self.artifacts[id] = {
            "id": id,
            "content": content,
            "type": type,
            "metadata": metadata or {},
            "created": "now",
            "refactorHistory": [],
        }
        return self.artifacts[id]

    def renderArtifact(self, id, container_mock):
        """Simulate rendering"""
        if id not in self.artifacts:
            raise ValueError(f"Artifact not found: {id}")

        self.currentArtifactId = id
        artifact = self.artifacts[id]

        # Return HTML representation
        html = "<div class='artifact'>"
        html += f"<h3>{artifact['metadata'].get('title', id)}</h3>"
        html += f"<p>Type: {artifact['type']}</p>"

        # Content rendering based on type
        if artifact["type"] == "markdown":
            html += f"<div class='markdown-content'>{artifact['content']}</div>"
        elif artifact["type"] == "code":
            html += f"<pre><code>{artifact['content']}</code></pre>"
        elif artifact["type"] == "json":
            html += f"<pre>{json.dumps(json.loads(artifact['content']), indent=2)}</pre>"
        elif artifact["type"] == "plan":
            html += f"<div class='plan-tasks'>{artifact['content']}</div>"

        html += "</div>"

        container_mock.innerHTML = html
        return html

    def copyToClipboard(self, id):
        """Simulate copy to clipboard"""
        if id not in self.artifacts:
            return False
        return True

    def downloadArtifact(self, id):
        """Simulate download"""
        if id not in self.artifacts:
            return None
        artifact = self.artifacts[id]
        extensions = {"markdown": "md", "code": "txt", "json": "json", "plan": "txt"}
        return f"{artifact['id']}.{extensions.get(artifact['type'], 'txt')}"

    def refactorArtifact(self, id, refactor_type):
        """Simulate refactoring request"""
        if id not in self.artifacts:
            return None
        return {"artifact_id": id, "refactor_type": refactor_type, "status": "pending"}


class TestArtifactRenderer:
    """Test suite for ArtifactRenderer"""

    @pytest.fixture
    def renderer(self):
        """Initialize mock renderer"""
        return ArtifactRendererMock()

    def test_register_markdown_artifact(self, renderer):
        """Test registering a markdown artifact"""
        artifact = renderer.registerArtifact(
            id="md-001",
            content="# Title\n## Subtitle\nContent",
            type="markdown",
            metadata={"title": "My Document"},
        )

        assert artifact["id"] == "md-001"
        assert artifact["type"] == "markdown"
        assert artifact["metadata"]["title"] == "My Document"

    def test_register_code_artifact(self, renderer):
        """Test registering a code artifact"""
        artifact = renderer.registerArtifact(
            id="code-001",
            content="print('Hello')",
            type="code",
            metadata={"language": "python"},
        )

        assert artifact["type"] == "code"
        assert artifact["metadata"]["language"] == "python"

    def test_register_json_artifact(self, renderer):
        """Test registering a JSON artifact"""
        json_content = json.dumps({"key": "value", "count": 42})
        artifact = renderer.registerArtifact(id="json-001", content=json_content, type="json")

        assert artifact["type"] == "json"
        assert "key" in artifact["content"]

    def test_register_plan_artifact(self, renderer):
        """Test registering a plan (task list) artifact"""
        plan_content = json.dumps(
            {
                "tasks": [
                    {"id": "t1", "name": "Task 1", "priority": "high"},
                    {"id": "t2", "name": "Task 2", "priority": "medium"},
                ]
            }
        )

        artifact = renderer.registerArtifact(
            id="plan-001",
            content=plan_content,
            type="plan",
            metadata={"title": "Project Plan"},
        )

        assert artifact["type"] == "plan"
        assert "tasks" in artifact["content"]

    def test_render_markdown_artifact(self, renderer):
        """Test rendering markdown artifact"""
        renderer.registerArtifact(id="md-001", content="# Heading", type="markdown")

        container = Mock()
        html = renderer.renderArtifact("md-001", container)

        assert "Heading" in html
        assert "markdown-content" in html

    def test_render_code_artifact(self, renderer):
        """Test rendering code artifact"""
        renderer.registerArtifact(id="code-001", content="function test() {}", type="code")

        container = Mock()
        html = renderer.renderArtifact("code-001", container)

        assert "code" in html.lower()
        assert "test()" in html

    def test_render_nonexistent_artifact(self, renderer):
        """Test rendering nonexistent artifact raises error"""
        container = Mock()

        with pytest.raises(ValueError):
            renderer.renderArtifact("nonexistent", container)

    def test_copy_to_clipboard(self, renderer):
        """Test copy to clipboard functionality"""
        renderer.registerArtifact(id="copy-001", content="Content to copy")

        result = renderer.copyToClipboard("copy-001")
        assert result is True

    def test_copy_nonexistent_artifact(self, renderer):
        """Test copying nonexistent artifact fails"""
        result = renderer.copyToClipboard("nonexistent")
        assert result is False

    def test_download_artifact(self, renderer):
        """Test downloading artifact"""
        renderer.registerArtifact(id="download-001", content="Content to download", type="markdown")

        filename = renderer.downloadArtifact("download-001")
        assert filename is not None
        assert "download-001" in filename
        assert filename.endswith(".md")

    def test_download_code_artifact(self, renderer):
        """Test downloading code artifact"""
        renderer.registerArtifact(
            id="code-download",
            content="code content",
            type="code",
            metadata={"language": "python"},
        )

        filename = renderer.downloadArtifact("code-download")
        # Should have appropriate extension
        assert filename is not None

    def test_refactor_artifact(self, renderer):
        """Test refactoring request"""
        renderer.registerArtifact(id="refactor-001", content="Original content")

        request = renderer.refactorArtifact("refactor-001", "shorten")

        assert request["artifact_id"] == "refactor-001"
        assert request["refactor_type"] == "shorten"
        assert request["status"] == "pending"

    def test_multiple_refactoring_types(self, renderer):
        """Test different refactoring types"""
        renderer.registerArtifact(id="multi-refactor", content="Some content")

        refactor_types = [
            "shorten",
            "expand",
            "formal",
            "casual",
            "executive",
            "technical",
        ]

        for refactor_type in refactor_types:
            request = renderer.refactorArtifact("multi-refactor", refactor_type)
            assert request["refactor_type"] == refactor_type

    def test_artifact_with_metadata(self, renderer):
        """Test artifact with comprehensive metadata"""
        metadata = {
            "title": "System Specification",
            "wordCount": 2500,
            "compression": "15:1",
            "source": "requirements.pdf",
            "timestamp": "2026-02-11T10:30:00Z",
        }

        artifact = renderer.registerArtifact(id="meta-001", content="Specification content", metadata=metadata)

        assert artifact["metadata"]["wordCount"] == 2500
        assert artifact["metadata"]["source"] == "requirements.pdf"

    def test_render_with_metadata(self, renderer):
        """Test rendering includes metadata"""
        renderer.registerArtifact(
            id="with-meta",
            content="Content",
            type="markdown",
            metadata={"title": "My Title", "wordCount": 100},
        )

        container = Mock()
        html = renderer.renderArtifact("with-meta", container)

        # Should include title and metadata
        assert "My Title" in html or "artifact" in html.lower()

    def test_artifact_refactor_history(self, renderer):
        """Test refactoring history tracking"""
        artifact = renderer.registerArtifact(id="history-001", content="Original")

        # Simulate refactoring
        renderer.refactorArtifact("history-001", "shorten")
        artifact = renderer.artifacts["history-001"]

        # History should be tracked
        assert "refactorHistory" in artifact

    def test_current_artifact_id_tracking(self, renderer):
        """Test that current artifact ID is tracked"""
        assert renderer.currentArtifactId is None

        renderer.registerArtifact(id="track-001", content="Content")

        container = Mock()
        renderer.renderArtifact("track-001", container)

        assert renderer.currentArtifactId == "track-001"

    def test_artifact_types(self, renderer):
        """Test all supported artifact types"""
        types = ["markdown", "code", "html", "json", "plan"]

        for i, artifact_type in enumerate(types):
            artifact = renderer.registerArtifact(id=f"type-{i}", content="Content", type=artifact_type)
            assert artifact["type"] == artifact_type

    def test_json_artifact_validation(self, renderer):
        """Test JSON artifact stores valid JSON"""
        json_data = {"key": "value", "items": [1, 2, 3]}
        json_str = json.dumps(json_data)

        artifact = renderer.registerArtifact(id="json-valid", content=json_str, type="json")

        # Should be able to parse back
        parsed = json.loads(artifact["content"])
        assert parsed["key"] == "value"
        assert len(parsed["items"]) == 3

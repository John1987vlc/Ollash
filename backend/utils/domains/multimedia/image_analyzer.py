"""Multimodal Image Analyzer

Enables the agent to analyze screenshots, architecture diagrams,
and other images using multimodal LLM models (llava, bakllava, etc.)
via the Ollama vision API.
"""

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


class ImageAnalyzer:
    """Analyzes images using multimodal LLM models via Ollama.

    Supports screenshot analysis for UI error detection,
    architecture diagram interpretation, and OCR-like text extraction.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(
        self,
        vision_client: Any,
        logger: AgentLogger,
        default_model: str = "llava",
    ):
        self.vision_client = vision_client
        self.logger = logger
        self.default_model = default_model

    def _load_image_base64(self, image_path: Path) -> Optional[str]:
        """Load an image file and return its base64 encoding."""
        image_path = Path(image_path)
        if not image_path.exists():
            self.logger.error(f"Image not found: {image_path}")
            return None
        if image_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            self.logger.error(f"Unsupported image format: {image_path.suffix}")
            return None
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Failed to load image {image_path}: {e}")
            return None

    async def analyze_screenshot(self, image_path: Path, question: str = "") -> str:
        """Analyze a screenshot of a UI error or application state.

        Args:
            image_path: Path to the screenshot image.
            question: Specific question about the screenshot.
                      If empty, provides a general analysis.

        Returns:
            Analysis text from the vision model.
        """
        image_b64 = self._load_image_base64(image_path)
        if not image_b64:
            return "Error: Could not load image."

        prompt = question or (
            "Analyze this screenshot. Identify any errors, warnings, or UI issues visible. "
            "If there are error messages, extract them. Describe the state of the application "
            "and suggest potential fixes for any issues found."
        )

        return await self._query_vision(prompt, image_b64)

    async def analyze_diagram(self, image_path: Path) -> Dict[str, Any]:
        """Interpret an architecture or system diagram.

        Args:
            image_path: Path to the diagram image.

        Returns:
            Dict with 'description', 'components', and 'relationships'.
        """
        image_b64 = self._load_image_base64(image_path)
        if not image_b64:
            return {"description": "Error: Could not load image.", "components": [], "relationships": []}

        prompt = (
            "Analyze this architecture/system diagram. Provide:\n"
            "1. A brief description of what the diagram represents\n"
            "2. List all components/services shown\n"
            "3. Describe the relationships/connections between components\n"
            "4. Identify the technology stack if visible\n"
            "Format your response clearly with sections."
        )

        response = await self._query_vision(prompt, image_b64)

        return {
            "description": response,
            "components": self._extract_list_items(response, "component"),
            "relationships": self._extract_list_items(response, "relationship"),
        }

    async def extract_text_from_image(self, image_path: Path) -> str:
        """Extract readable text from an image (OCR-like functionality).

        Args:
            image_path: Path to the image containing text.

        Returns:
            Extracted text content.
        """
        image_b64 = self._load_image_base64(image_path)
        if not image_b64:
            return ""

        prompt = (
            "Extract ALL readable text from this image. "
            "Preserve the layout and formatting as much as possible. "
            "Include any code, error messages, labels, and annotations. "
            "Return only the extracted text, nothing else."
        )

        return await self._query_vision(prompt, image_b64)

    async def suggest_code_fix(self, screenshot_path: Path, context: str = "") -> str:
        """Analyze a screenshot showing a code error and suggest a fix.

        Args:
            screenshot_path: Path to the screenshot showing the error.
            context: Additional context about the project/file.

        Returns:
            Suggested code fix based on the visible error.
        """
        image_b64 = self._load_image_base64(screenshot_path)
        if not image_b64:
            return "Error: Could not load image."

        prompt = (
            "This screenshot shows a code error or bug. "
            "1. Identify the error type and message\n"
            "2. Determine the root cause\n"
            "3. Suggest a specific code fix\n"
        )
        if context:
            prompt += f"\nProject context: {context}"

        return await self._query_vision(prompt, image_b64)

    async def _query_vision(self, prompt: str, image_b64: str) -> str:
        """Send a vision query to the multimodal model."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ]

            response = self.vision_client.chat(
                messages=messages,
            )

            if isinstance(response, dict):
                content = response.get("message", {}).get("content", "")
            else:
                content = str(response)

            return content.strip()
        except Exception as e:
            self.logger.error(f"Vision model query failed: {e}")
            return f"Error: Vision analysis failed - {e}"

    @staticmethod
    def _extract_list_items(text: str, item_type: str) -> List[str]:
        """Extract list items from structured text response."""
        items = []
        for line in text.split("\n"):
            line = line.strip()
            if line and (line.startswith("-") or line.startswith("*") or line[0:1].isdigit()):
                cleaned = line.lstrip("-*0123456789. ").strip()
                if cleaned:
                    items.append(cleaned)
        return items

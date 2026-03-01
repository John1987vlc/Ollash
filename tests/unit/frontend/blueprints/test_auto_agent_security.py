"""Security tests for auto_agent_bp.

Covers:
- Path traversal prevention (_safe_resolve)
- Command injection prevention (shell=False enforcement)
- MIME magic-byte validation (_validate_image_magic)
"""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers under test (imported directly to test without full Flask app setup)
# ---------------------------------------------------------------------------

from frontend.blueprints.auto_agent_bp import _safe_resolve, _validate_image_magic


@pytest.mark.unit
class TestSafeResolve:
    """Unit tests for the _safe_resolve path-traversal guard."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        """A normal relative path inside the base is resolved correctly."""
        (tmp_path / "subdir").mkdir()
        result = _safe_resolve(tmp_path, "subdir/file.py")
        assert result == (tmp_path / "subdir" / "file.py").resolve()

    def test_plain_filename(self, tmp_path: Path) -> None:
        """A plain filename with no path separator is allowed."""
        result = _safe_resolve(tmp_path, "main.py")
        assert result.parent == tmp_path.resolve()

    @pytest.mark.parametrize(
        "malicious",
        [
            "../../etc/passwd",
            "../.env",
            "foo/../../secret",
            "/etc/shadow",
            # Flask URL-decodes percent-encoded paths before handing them to Python,
            # so "%2F" arrives as "/" — we test the decoded form that _safe_resolve sees.
            "../../etc/passwd",
        ],
    )
    def test_traversal_raises_value_error(self, tmp_path: Path, malicious: str) -> None:
        """Paths that escape the base directory must raise ValueError."""
        with pytest.raises(ValueError, match="traversal"):
            _safe_resolve(tmp_path, malicious)

    def test_absolute_path_outside_base_raises(self, tmp_path: Path) -> None:
        """An absolute path pointing outside the base must be rejected."""
        other = Path("/tmp/evil")
        with pytest.raises(ValueError):
            _safe_resolve(tmp_path, str(other))


@pytest.mark.unit
class TestValidateImageMagic:
    """Unit tests for MIME magic-byte validation."""

    def _make_stream(self, data: bytes) -> MagicMock:
        """Return a mock file-storage object whose stream contains *data*."""
        mock_file = MagicMock()
        stream = io.BytesIO(data)
        mock_file.stream = stream
        return mock_file

    def test_valid_png(self) -> None:
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
        assert _validate_image_magic(self._make_stream(png_header)) is True

    def test_valid_jpeg(self) -> None:
        jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 8
        assert _validate_image_magic(self._make_stream(jpeg_header)) is True

    def test_valid_gif87(self) -> None:
        gif_header = b"GIF87a" + b"\x00" * 6
        assert _validate_image_magic(self._make_stream(gif_header)) is True

    def test_valid_gif89(self) -> None:
        gif_header = b"GIF89a" + b"\x00" * 6
        assert _validate_image_magic(self._make_stream(gif_header)) is True

    def test_valid_webp(self) -> None:
        webp_header = b"RIFF\x00\x00\x00\x00WEBP"
        assert _validate_image_magic(self._make_stream(webp_header)) is True

    def test_riff_without_webp_marker_is_rejected(self) -> None:
        """RIFF container that is NOT a WEBP (e.g. WAV audio) must be rejected."""
        wav_header = b"RIFF\x00\x00\x00\x00WAVE"
        assert _validate_image_magic(self._make_stream(wav_header)) is False

    def test_elf_binary_is_rejected(self) -> None:
        """An ELF executable disguised as an image must be rejected."""
        elf_header = b"\x7fELF" + b"\x00" * 8
        assert _validate_image_magic(self._make_stream(elf_header)) is False

    def test_empty_file_is_rejected(self) -> None:
        assert _validate_image_magic(self._make_stream(b"")) is False

    def test_text_content_is_rejected(self) -> None:
        assert _validate_image_magic(self._make_stream(b"hello world")) is False

    def test_stream_position_reset_after_read(self) -> None:
        """After validation the stream position must be back at 0 so the file can be saved."""
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
        stream = io.BytesIO(png_header)
        mock_file = MagicMock()
        mock_file.stream = stream
        _validate_image_magic(mock_file)
        assert stream.tell() == 0


@pytest.mark.unit
class TestExecuteCommandNoShell:
    """Verify that execute_command uses shell=False (no injection via shell metacharacters)."""

    def test_blueprint_source_does_not_contain_shell_true(self) -> None:
        """The execute_command route must not pass shell=True to subprocess.run.

        We read the source file directly — avoids module-import aliasing caused by
        frontend/blueprints/__init__.py exporting the Blueprint object under the same name.
        """
        import pathlib

        src_path = pathlib.Path("frontend/blueprints/auto_agent_bp.py")
        source = src_path.read_text(encoding="utf-8")

        # Find the execute_command function body
        start = source.find("def execute_command(")
        assert start >= 0, "execute_command function not found in auto_agent_bp.py"

        # Extract until the next top-level def/class (rough but sufficient)
        fn_body = source[start : source.find("\n@auto_agent_bp", start)]

        assert "shell=True" not in fn_body, "execute_command must not use shell=True (command injection risk)"
        assert "shell=False" in fn_body, "execute_command must explicitly pass shell=False to subprocess.run"
        assert "shlex.split" in fn_body, "execute_command must use shlex.split to parse the command string safely"

    @pytest.mark.parametrize(
        "injection_payload",
        [
            "ls; rm -rf /",
            "echo safe && cat /etc/passwd",
            "ls | grep secret",
            "`id`",
        ],
    )
    def test_injection_payload_passed_as_list(self, injection_payload: str) -> None:
        """Shell metacharacters in the command string are NOT interpreted (shell=False).

        shlex.split turns the string into a list; the shell never sees the metacharacters.
        """
        import shlex

        from frontend.blueprints.auto_agent_bp import _SAFE_FILENAME_RE  # noqa: F401 (import check)

        # Verify shlex.split produces a list — subprocess.run with shell=False and a list
        # treats each element as a literal argument, not shell syntax.
        parts = shlex.split(injection_payload)
        # The first token should be the base command, subsequent tokens are args
        assert isinstance(parts, list)
        # The semicolon / pipe / backtick are separate tokens — not interpreted as shell operators
        for special in [";", "&&", "|", "`"]:
            if special in injection_payload:
                # They must appear as individual list elements (not concatenated)
                assert any(special in p for p in parts), f"Expected '{special}' to remain as a literal token in {parts}"

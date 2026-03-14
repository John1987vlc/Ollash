"""
backend/cli/file_editor.py
Visual diff display + CodePatcher-based file editing for the CLI.

Usage:
    editor = FileEditor(console, repo_root)
    editor.propose_edit(file_path, new_content)   # shows diff, asks confirmation
    editor.apply_patch(file_path, patch_text)      # unified diff patch
"""

from __future__ import annotations

import difflib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


class FileEditor:
    """Shows coloured diffs and applies edits with user confirmation."""

    def __init__(self, console: Console, root: Path | str) -> None:
        self.console = console
        self.root = Path(root).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propose_edit(self, path: str | Path, new_content: str, auto_confirm: bool = False) -> bool:
        """
        Show a coloured unified diff between the current file and `new_content`.
        Asks the user to confirm, then applies the change via CodePatcher.
        Returns True if the edit was applied.
        """
        p = self._resolve(path)
        old_content = ""
        if p.exists():
            try:
                old_content = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass

        if old_content == new_content:
            self.console.print(f"[dim]No changes for {p.relative_to(self.root)}[/dim]")
            return False

        self._print_diff(old_content, new_content, str(p.relative_to(self.root)))

        if not auto_confirm:
            from rich.prompt import Confirm

            if not Confirm.ask("[bold green]Apply this edit?[/bold green]", default=True):
                self.console.print("[dim]Edit discarded.[/dim]")
                return False

        return self._write(p, new_content)

    def propose_patch(self, path: str | Path, patch_text: str, auto_confirm: bool = False) -> bool:
        """
        Apply a unified diff patch string to a file using CodePatcher.
        Returns True if applied successfully.
        """
        p = self._resolve(path)
        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher

            patcher = CodePatcher.__new__(CodePatcher)
            result = patcher.apply_patch(str(p), patch_text)
            if result:
                self.console.print(f"[green]Patch applied to {p.name}[/green]")
                return True
            self.console.print(f"[yellow]Patch did not apply cleanly to {p.name}[/yellow]")
            return False
        except Exception as e:
            self.console.print(f"[red]Patch error: {e}[/red]")
            return False

    def show_file(self, path: str | Path, max_lines: int = 80) -> None:
        """Display a file with syntax highlighting."""
        p = self._resolve(path)
        if not p.exists():
            self.console.print(f"[red]File not found: {path}[/red]")
            return
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more lines]"
            self.console.print(
                Panel(
                    Syntax(content, p.suffix.lstrip(".") or "text", theme="monokai", line_numbers=True),
                    title=f"[bold]{p.relative_to(self.root)}[/bold]",
                    border_style="blue",
                )
            )
        except Exception as e:
            self.console.print(f"[red]Error reading file: {e}[/red]")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        return p.resolve()

    def _print_diff(self, old: str, new: str, label: str) -> None:
        diff = list(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{label}",
                tofile=f"b/{label}",
                lineterm="",
            )
        )
        if not diff:
            return

        colored_lines: list[Text] = []
        for line in diff[:300]:  # cap at 300 diff lines for readability
            if line.startswith("+++") or line.startswith("---"):
                colored_lines.append(Text(line, style="bold white"))
            elif line.startswith("@@"):
                colored_lines.append(Text(line, style="cyan"))
            elif line.startswith("+"):
                colored_lines.append(Text(line, style="green"))
            elif line.startswith("-"):
                colored_lines.append(Text(line, style="red"))
            else:
                colored_lines.append(Text(line, style="dim"))

        from rich.console import Group as RichGroup

        self.console.print(
            Panel(
                RichGroup(*colored_lines),
                title=f"[bold yellow]Proposed changes to {label}[/bold yellow]",
                border_style="yellow",
            )
        )

    def _write(self, path: Path, content: str) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.console.print(f"[green]✓ Saved {path.name}[/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Failed to write {path}: {e}[/red]")
            return False

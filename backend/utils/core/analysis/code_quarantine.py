"""
Code Quarantine for the Ollash Agent Framework.

This module provides a class to quarantine code that is deemed unsafe
or unstable. Quarantined code can be reviewed by the user before being
integrated into the project.
"""

import shutil
from pathlib import Path
from typing import List

from backend.utils.core.system.agent_logger import AgentLogger


class CodeQuarantine:
    """Manages the code quarantine area."""

    def __init__(self, project_root: Path, logger: AgentLogger):
        """
        Initializes the CodeQuarantine.

        Args:
            project_root: The root directory of the project.
            logger: The logger instance.
        """
        self.quarantine_dir = project_root / ".quarantine"
        self.quarantine_dir.mkdir(exist_ok=True)
        self.logger = logger

    def quarantine_file(self, file_path: Path) -> bool:
        """
        Moves a file to the quarantine directory.

        Args:
            file_path: The path to the file to quarantine.

        Returns:
            True if the file was successfully quarantined, False otherwise.
        """
        if not file_path.exists():
            self.logger.warning(f"File to quarantine not found: {file_path}")
            return False

        try:
            quarantine_path = self.quarantine_dir / file_path.name
            shutil.move(str(file_path), str(quarantine_path))
            self.logger.info(f"Quarantined file: {file_path} -> {quarantine_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to quarantine file {file_path}: {e}")
            return False

    def get_quarantined_files(self) -> List[Path]:
        """
        Gets a list of all files in the quarantine directory.

        Returns:
            A list of paths to the quarantined files.
        """
        return list(self.quarantine_dir.glob("*"))

    def restore_file(self, file_name: str, destination: Path) -> bool:
        """
        Restores a file from quarantine to a specified destination.

        Args:
            file_name: The name of the file to restore.
            destination: The path to restore the file to.

        Returns:
            True if the file was successfully restored, False otherwise.
        """
        quarantine_path = self.quarantine_dir / file_name
        if not quarantine_path.exists():
            self.logger.warning(f"File not found in quarantine: {file_name}")
            return False

        try:
            shutil.move(str(quarantine_path), str(destination))
            self.logger.info(f"Restored file: {quarantine_path} -> {destination}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore file {file_name}: {e}")
            return False

"""
License Checker for the Ollash Agent Framework.

This module provides a class to check for license compliance in the
generated code.
"""

from typing import List, Dict, Any
from pathlib import Path

from src.utils.core.agent_logger import AgentLogger

class LicenseChecker:
    """Checks for license compliance."""

    def __init__(self, logger: AgentLogger, config: Dict[str, Any]):
        """
        Initializes the LicenseChecker.

        Args:
            logger: The logger instance.
            config: The agent's configuration.
        """
        self.logger = logger
        self.config = config.get("license_checker", {})
        self.allowed_licenses = self.config.get("allowed_licenses", ["MIT", "Apache-2.0", "GPL-3.0"])

    def check_file_license(self, file_path: Path) -> bool:
        """
        Checks the license of a file.

        Args:
            file_path: The path to the file.

        Returns:
            True if the license is compliant, False otherwise.
        """
        if not file_path.exists():
            self.logger.warning(f"File not found for license check: {file_path}")
            return True # Assume compliant if file doesn't exist

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(1024) # Read first 1KB to find license
            
            for license_name in self.allowed_licenses:
                if license_name.lower() in content.lower():
                    return True
            
            # A more sophisticated check would use a proper license scanning tool
            # For now, we'll just check for the presence of the license name.
            if "license" in content.lower():
                self.logger.warning(f"Potentially non-compliant license in {file_path}")
                return False

            return True # No license found, assume compliant for now
        except Exception as e:
            self.logger.error(f"Failed to check license for file {file_path}: {e}")
            return False

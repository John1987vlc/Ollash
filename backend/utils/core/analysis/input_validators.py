"""
Input Validators

Utility functions for validating user input such as git URLs
and project names.
"""

import re
from urllib.parse import urlparse


def validate_git_url(url: str) -> bool:
    """Validate that a URL is a safe git repository URL.

    Only allows HTTPS and git:// protocols. Rejects SSH, file://, and
    other potentially dangerous schemes.

    Args:
        url: The git URL to validate.

    Returns:
        True if the URL is valid and safe.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # Allow HTTPS and git protocols only
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "git"):
        return False

    # Must have a valid hostname
    if not parsed.netloc:
        return False

    # Basic path check — must have at least owner/repo
    path = parsed.path.strip("/")
    if not path or "/" not in path:
        return False

    return True


def validate_project_name(name: str) -> bool:
    """Validate a project name for filesystem safety.

    Args:
        name: The project name to validate.

    Returns:
        True if the name is safe for use as a directory name.
    """
    if not name or not isinstance(name, str):
        return False

    # Allow alphanumeric, hyphens, underscores, dots
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$", name))

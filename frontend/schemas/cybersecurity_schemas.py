"""Request schemas for the Cybersecurity blueprint."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class PortScanRequest(BaseModel):
    """Body for POST /api/cybersecurity/scan/ports."""

    host: str = Field(
        ...,
        min_length=1,
        max_length=253,
        description="Hostname or IP address to scan.",
    )
    common_ports_only: bool = Field(
        default=True,
        description="When True, scan only the most common ports.",
    )

    @field_validator("host")
    @classmethod
    def host_no_shell_chars(cls, v: str) -> str:
        """Reject shell metacharacters to prevent command injection."""
        forbidden = set(";&|`$><\n\r\t")
        if any(ch in forbidden for ch in v):
            raise ValueError("host contains disallowed characters")
        return v.strip()


class VulnScanRequest(BaseModel):
    """Body for POST /api/cybersecurity/scan/vulnerabilities."""

    path: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Relative path to the file to scan.",
    )


class IntegrityCheckRequest(BaseModel):
    """Body for POST /api/cybersecurity/integrity/check."""

    path: str = Field(..., min_length=1, max_length=512)
    expected_hash: str = Field(..., min_length=1, max_length=256)
    algorithm: str = Field(
        default="sha256",
        pattern=r"^(sha256|sha512|md5|sha1)$",
        description="Hash algorithm to use.",
    )


class LogAnalysisRequest(BaseModel):
    """Body for POST /api/cybersecurity/logs/analyze."""

    path: str = Field(..., min_length=1, max_length=512)
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Optional list of keywords to look for in the log.",
    )

"""
Deep License Scanner

Scans dependency trees for license conflicts and generates compatibility reports.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from backend.utils.core.agent_logger import AgentLogger


# License compatibility matrix
LICENSE_COMPATIBILITY: Dict[str, Dict[str, List[str]]] = {
    "MIT": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "Unlicense", "0BSD", "CC0-1.0"],
        "incompatible": [],
    },
    "Apache-2.0": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "Unlicense"],
        "incompatible": ["GPL-2.0-only"],
    },
    "GPL-2.0-only": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "GPL-2.0-only", "LGPL-2.1-only", "ISC"],
        "incompatible": ["Apache-2.0", "GPL-3.0-only"],
    },
    "GPL-3.0-only": {
        "compatible": [
            "MIT",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "Apache-2.0",
            "GPL-2.0-only",
            "GPL-3.0-only",
            "LGPL-2.1-only",
            "LGPL-3.0-only",
            "ISC",
        ],
        "incompatible": [],
    },
    "LGPL-2.1-only": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "LGPL-2.1-only", "GPL-2.0-only"],
        "incompatible": [],
    },
    "LGPL-3.0-only": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "LGPL-3.0-only", "GPL-3.0-only"],
        "incompatible": [],
    },
    "BSD-2-Clause": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"],
        "incompatible": [],
    },
    "BSD-3-Clause": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"],
        "incompatible": [],
    },
    "ISC": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"],
        "incompatible": [],
    },
    "MPL-2.0": {
        "compatible": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "MPL-2.0", "GPL-3.0-only"],
        "incompatible": ["GPL-2.0-only"],
    },
}

# Known package licenses (common packages)
KNOWN_LICENSES: Dict[str, str] = {
    # Python
    "flask": "BSD-3-Clause",
    "django": "BSD-3-Clause",
    "requests": "Apache-2.0",
    "numpy": "BSD-3-Clause",
    "pandas": "BSD-3-Clause",
    "pytest": "MIT",
    "fastapi": "MIT",
    "pydantic": "MIT",
    "sqlalchemy": "MIT",
    "celery": "BSD-3-Clause",
    "redis": "MIT",
    "pillow": "MIT-CMU",
    "boto3": "Apache-2.0",
    "click": "BSD-3-Clause",
    "jinja2": "BSD-3-Clause",
    "werkzeug": "BSD-3-Clause",
    "aiohttp": "Apache-2.0",
    "cryptography": "Apache-2.0",
    # Node.js
    "express": "MIT",
    "react": "MIT",
    "vue": "MIT",
    "lodash": "MIT",
    "axios": "MIT",
    "next": "MIT",
    "typescript": "Apache-2.0",
    "webpack": "MIT",
    "jest": "MIT",
    "mocha": "MIT",
}


@dataclass
class DependencyLicense:
    """License information for a single dependency."""

    package_name: str
    version: str
    license_id: str  # SPDX identifier
    license_name: str
    source: str  # "known", "detected", "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package_name,
            "version": self.version,
            "license": self.license_id,
            "license_name": self.license_name,
            "source": self.source,
        }


@dataclass
class LicenseConflict:
    """A detected license incompatibility."""

    package_name: str
    package_license: str
    project_license: str
    reason: str
    severity: str = "warning"  # "warning" or "blocking"


@dataclass
class CompatibilityReport:
    """License compatibility analysis result."""

    project_license: str
    total_dependencies: int
    compatible_count: int
    incompatible_count: int
    unknown_count: int
    conflicts: List[LicenseConflict]
    dependencies: List[DependencyLicense]

    @property
    def is_compliant(self) -> bool:
        return self.incompatible_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_license": self.project_license,
            "total_dependencies": self.total_dependencies,
            "compatible": self.compatible_count,
            "incompatible": self.incompatible_count,
            "unknown": self.unknown_count,
            "is_compliant": self.is_compliant,
            "conflicts": [
                {
                    "package": c.package_name,
                    "license": c.package_license,
                    "reason": c.reason,
                    "severity": c.severity,
                }
                for c in self.conflicts
            ],
            "dependencies": [d.to_dict() for d in self.dependencies],
        }


class DeepLicenseScanner:
    """Deep scanner for library license compatibility.

    Checks requirements files for license information and validates
    compatibility with the project's chosen license.
    """

    def __init__(self, logger: AgentLogger):
        self.logger = logger

    def scan_python_deps(self, requirements_content: str) -> List[DependencyLicense]:
        """Parse Python requirements.txt and identify licenses."""
        deps = []
        for line in requirements_content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Parse package==version or package>=version etc
            match = re.match(r"^([a-zA-Z0-9_-]+)\s*(?:[><=!~]+\s*(.+?))?(?:\s*;.*)?$", line)
            if not match:
                continue

            pkg_name = match.group(1).lower().replace("-", "_")
            version = match.group(2) or "latest"

            known = KNOWN_LICENSES.get(pkg_name) or KNOWN_LICENSES.get(pkg_name.replace("_", "-"))
            if known:
                deps.append(
                    DependencyLicense(
                        package_name=pkg_name,
                        version=version,
                        license_id=known,
                        license_name=known,
                        source="known",
                    )
                )
            else:
                deps.append(
                    DependencyLicense(
                        package_name=pkg_name,
                        version=version,
                        license_id="UNKNOWN",
                        license_name="Unknown",
                        source="unknown",
                    )
                )

        return deps

    def scan_node_deps(self, package_json_content: str) -> List[DependencyLicense]:
        """Parse package.json and identify licenses."""
        deps = []
        try:
            pkg = json.loads(package_json_content)
        except json.JSONDecodeError:
            return deps

        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_deps.update(pkg.get("devDependencies", {}))

        for pkg_name, version in all_deps.items():
            known = KNOWN_LICENSES.get(pkg_name)
            if known:
                deps.append(
                    DependencyLicense(
                        package_name=pkg_name,
                        version=version,
                        license_id=known,
                        license_name=known,
                        source="known",
                    )
                )
            else:
                deps.append(
                    DependencyLicense(
                        package_name=pkg_name,
                        version=version,
                        license_id="UNKNOWN",
                        license_name="Unknown",
                        source="unknown",
                    )
                )

        return deps

    def check_compatibility(self, project_license: str, deps: List[DependencyLicense]) -> CompatibilityReport:
        """Check license compatibility for all dependencies."""
        compatible_count = 0
        incompatible_count = 0
        unknown_count = 0
        conflicts = []

        compat_info = LICENSE_COMPATIBILITY.get(project_license, {})
        compatible_licenses = compat_info.get("compatible", [])
        incompatible_licenses = compat_info.get("incompatible", [])

        for dep in deps:
            if dep.license_id == "UNKNOWN":
                unknown_count += 1
                continue

            if dep.license_id in incompatible_licenses:
                incompatible_count += 1
                conflicts.append(
                    LicenseConflict(
                        package_name=dep.package_name,
                        package_license=dep.license_id,
                        project_license=project_license,
                        reason=f"{dep.license_id} is incompatible with {project_license}",
                        severity="blocking",
                    )
                )
            elif dep.license_id in compatible_licenses or dep.license_id == project_license:
                compatible_count += 1
            else:
                # Not explicitly listed - treat as warning
                unknown_count += 1
                conflicts.append(
                    LicenseConflict(
                        package_name=dep.package_name,
                        package_license=dep.license_id,
                        project_license=project_license,
                        reason=f"Compatibility of {dep.license_id} with {project_license} is uncertain",
                        severity="warning",
                    )
                )

        return CompatibilityReport(
            project_license=project_license,
            total_dependencies=len(deps),
            compatible_count=compatible_count,
            incompatible_count=incompatible_count,
            unknown_count=unknown_count,
            conflicts=conflicts,
            dependencies=deps,
        )

    def scan_project(self, generated_files: Dict[str, str], project_license: str = "MIT") -> CompatibilityReport:
        """Scan all dependency files in a project and check compatibility."""
        all_deps: List[DependencyLicense] = []

        for file_path, content in generated_files.items():
            if file_path.endswith("requirements.txt"):
                all_deps.extend(self.scan_python_deps(content))
            elif file_path.endswith("package.json"):
                all_deps.extend(self.scan_node_deps(content))

        report = self.check_compatibility(project_license, all_deps)

        self.logger.info(
            f"License scan: {report.total_dependencies} deps, "
            f"{report.compatible_count} compatible, {report.incompatible_count} incompatible, "
            f"{report.unknown_count} unknown"
        )

        return report

    def generate_report_markdown(self, report: CompatibilityReport) -> str:
        """Generate a LICENSE_REPORT.md from a compatibility report."""
        lines = [
            "# License Compliance Report\n",
            f"**Project License:** {report.project_license}\n",
            f"**Total Dependencies:** {report.total_dependencies}\n",
            f"**Status:** {'COMPLIANT' if report.is_compliant else 'NON-COMPLIANT'}\n",
            "",
            "## Summary\n",
            f"- Compatible: {report.compatible_count}",
            f"- Incompatible: {report.incompatible_count}",
            f"- Unknown: {report.unknown_count}",
            "",
        ]

        if report.conflicts:
            lines.append("## Conflicts\n")
            for c in report.conflicts:
                icon = "BLOCKING" if c.severity == "blocking" else "WARNING"
                lines.append(f"- **[{icon}]** `{c.package_name}` ({c.package_license}): {c.reason}")
            lines.append("")

        lines.append("## Dependencies\n")
        lines.append("| Package | Version | License | Status |")
        lines.append("|---------|---------|---------|--------|")
        for d in report.dependencies:
            status = "Compatible" if d.license_id != "UNKNOWN" else "Unknown"
            if any(c.package_name == d.package_name and c.severity == "blocking" for c in report.conflicts):
                status = "INCOMPATIBLE"
            lines.append(f"| {d.package_name} | {d.version} | {d.license_id} | {status} |")

        return "\n".join(lines)

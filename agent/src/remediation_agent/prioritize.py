"""Groups Inspector findings by package and ranks the groups.

Deterministic on purpose (ADR 0001): the model receives one compact entry per package
instead of every raw finding, and decides only what needs judgment (fix version,
reachability, breaking changes).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
OS_PACKAGE_MANAGERS = {"OS", "DEB", "APK", "RPM", "DPKG"}


class Source(StrEnum):
    """Where a vulnerable package comes from - decides how it can be fixed (lesson 4)."""

    DIRECT = "direct"  # listed in package.json -> bump it
    TRANSITIVE = "transitive"  # pulled in by another package -> bump the parent or use overrides
    APPLICATION = "application"  # in the app's node_modules, package.json not given
    BASE_IMAGE = "base-image"  # OS packages, Node.js runtime, bundled npm -> newer base image


@dataclass(frozen=True)
class Finding:
    vulnerability_id: str
    severity: str
    package: str
    installed_version: str
    fixed_in_version: str | None
    file_path: str | None
    package_manager: str | None
    exploit_available: bool
    epss: float
    inspector_score: float


@dataclass
class PackageGroup:
    package: str
    installed_version: str
    source: Source
    severity: str
    exploit_available: bool
    max_epss: float
    vulnerability_ids: list[str] = field(default_factory=list)
    fix_versions: list[str] = field(default_factory=list)
    prerelease_fix: bool = False

    @property
    def finding_count(self) -> int:
        return len(self.vulnerability_ids)


def from_inspector(raw: dict) -> Finding:
    """Normalizes one finding as returned by the Inspector ListFindings API."""
    details = raw.get("packageVulnerabilityDetails", {})
    pkg = (details.get("vulnerablePackages") or [{}])[0]
    fixed = pkg.get("fixedInVersion")
    return Finding(
        vulnerability_id=details.get("vulnerabilityId", raw.get("title", "unknown")),
        severity=raw.get("severity", "UNTRIAGED"),
        package=pkg.get("name", "unknown"),
        installed_version=pkg.get("version", "unknown"),
        fixed_in_version=None if fixed in (None, "", "NotAvailable") else fixed,
        file_path=pkg.get("filePath"),
        package_manager=pkg.get("packageManager"),
        exploit_available=raw.get("exploitAvailable") == "YES",
        epss=raw.get("epss", {}).get("score", 0.0),
        inspector_score=raw.get("inspectorScore", 0.0),
    )


def classify_source(finding: Finding, direct_dependencies: set[str] | None = None) -> Source:
    path = finding.file_path or ""
    # Globally installed modules (e.g. the npm bundled with Node.js) come with the base image;
    # an app may still live under /usr/src/app, so only /lib/node_modules/ counts as global.
    if (
        "/node_modules/" not in path
        or "/lib/node_modules/" in path
        or (finding.package_manager or "").upper() in OS_PACKAGE_MANAGERS
    ):
        return Source.BASE_IMAGE
    if direct_dependencies is None:
        return Source.APPLICATION
    return Source.DIRECT if finding.package in direct_dependencies else Source.TRANSITIVE


def is_prerelease(version: str) -> bool:
    """npm-style pre-release such as 5.0.0-beta.3 (lesson 10)."""
    return bool(re.search(r"-(alpha|beta|rc|pre|next|canary)", version, re.IGNORECASE))


def _version_key(version: str) -> tuple:
    numbers = [int(n) for n in re.findall(r"\d+", version.split("-")[0])]
    return (*numbers, 0 if is_prerelease(version) else 1)


def group_by_package(
    findings: Iterable[Finding], direct_dependencies: set[str] | None = None
) -> list[PackageGroup]:
    groups: dict[tuple[str, str, str | None], PackageGroup] = {}
    for f in findings:
        key = (f.package, f.installed_version, f.file_path)
        group = groups.get(key)
        if group is None:
            group = groups[key] = PackageGroup(
                package=f.package,
                installed_version=f.installed_version,
                source=classify_source(f, direct_dependencies),
                severity=f.severity,
                exploit_available=False,
                max_epss=0.0,
            )
        group.vulnerability_ids.append(f.vulnerability_id)
        if SEVERITY_RANK.get(f.severity, 0) > SEVERITY_RANK.get(group.severity, 0):
            group.severity = f.severity
        group.exploit_available |= f.exploit_available
        group.max_epss = max(group.max_epss, f.epss)
        if f.fixed_in_version and f.fixed_in_version not in group.fix_versions:
            group.fix_versions.append(f.fixed_in_version)

    for group in groups.values():
        group.fix_versions.sort(key=_version_key)
        group.prerelease_fix = any(is_prerelease(v) for v in group.fix_versions)
    return prioritize(groups.values())


def prioritize(groups: Iterable[PackageGroup]) -> list[PackageGroup]:
    """Ranks by severity, then known exploit, then EPSS, then number of findings.

    A plain sort key instead of a weighted score keeps the order explainable.
    """
    return sorted(
        groups,
        key=lambda g: (
            SEVERITY_RANK.get(g.severity, 0),
            g.exploit_available,
            g.max_epss,
            g.finding_count,
        ),
        reverse=True,
    )

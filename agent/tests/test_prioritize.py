from remediation_agent.prioritize import (
    Finding,
    Source,
    classify_source,
    from_inspector,
    group_by_package,
)


def finding(package="lodash", vuln="CVE-1", severity="HIGH", fixed="4.18.0", **overrides):
    values = {
        "vulnerability_id": vuln,
        "severity": severity,
        "package": package,
        "installed_version": "1.0.0",
        "fixed_in_version": fixed,
        "file_path": f"/app/node_modules/{package}/package.json",
        "package_manager": "NODE",
        "exploit_available": False,
        "epss": 0.0,
        "inspector_score": 5.0,
    }
    return Finding(**(values | overrides))


def test_from_inspector_reads_the_api_shape():
    raw = {
        "title": "CVE-2026-4800 - lodash",
        "severity": "CRITICAL",
        "inspectorScore": 9.8,
        "exploitAvailable": "YES",
        "epss": {"score": 0.12},
        "packageVulnerabilityDetails": {
            "vulnerabilityId": "CVE-2026-4800",
            "vulnerablePackages": [
                {
                    "name": "lodash",
                    "version": "4.17.20",
                    "fixedInVersion": "4.18.0",
                    "filePath": "/app/node_modules/lodash/package.json",
                    "packageManager": "NODE",
                }
            ],
        },
    }

    f = from_inspector(raw)

    assert (f.vulnerability_id, f.package, f.fixed_in_version) == (
        "CVE-2026-4800",
        "lodash",
        "4.18.0",
    )
    assert f.exploit_available and f.epss == 0.12


def test_from_inspector_treats_not_available_as_no_fix():
    raw = {
        "packageVulnerabilityDetails": {"vulnerablePackages": [{"fixedInVersion": "NotAvailable"}]}
    }

    assert from_inspector(raw).fixed_in_version is None


def test_classify_source():
    app = finding(file_path="/usr/src/app/node_modules/qs/package.json", package="qs")
    bundled_npm = finding(
        file_path="/usr/local/lib/node_modules/npm/node_modules/glob/package.json"
    )
    os_package = finding(file_path=None, package_manager="OS")
    node_binary = finding(file_path="/usr/local/bin/node", package_manager="NODEJS")

    assert classify_source(app) == Source.APPLICATION
    assert classify_source(app, {"express"}) == Source.TRANSITIVE
    assert classify_source(finding(), {"lodash"}) == Source.DIRECT
    assert classify_source(bundled_npm, {"glob"}) == Source.BASE_IMAGE
    assert classify_source(os_package) == Source.BASE_IMAGE
    assert classify_source(node_binary) == Source.BASE_IMAGE


def test_groups_findings_of_one_package():
    groups = group_by_package(
        [
            finding(vuln="CVE-1", severity="MEDIUM", fixed="4.17.21"),
            finding(vuln="CVE-2", severity="CRITICAL", fixed="4.18.0", exploit_available=True),
            finding(vuln="CVE-3", severity="LOW", fixed="4.18.0", epss=0.3),
        ]
    )

    assert len(groups) == 1
    lodash = groups[0]
    assert lodash.finding_count == 3
    assert lodash.severity == "CRITICAL"
    assert lodash.exploit_available and lodash.max_epss == 0.3
    assert lodash.fix_versions == ["4.17.21", "4.18.0"]


def test_sorts_fix_versions_numerically_and_flags_pre_releases():
    groups = group_by_package(
        [
            finding(package="express", vuln="A", fixed="5.1.0"),
            finding(package="express", vuln="B", fixed="5.0.0-beta.3"),
            finding(package="express", vuln="C", fixed="5.0.0"),
            finding(package="express", vuln="D", fixed="4.20.0"),
        ]
    )

    assert groups[0].fix_versions == ["4.20.0", "5.0.0-beta.3", "5.0.0", "5.1.0"]
    assert groups[0].prerelease_fix


def test_ranks_by_severity_then_exploit_then_epss_then_count():
    groups = group_by_package(
        [
            finding(package="low-many", vuln="1", severity="LOW"),
            finding(package="low-many", vuln="2", severity="LOW"),
            finding(package="high", severity="HIGH"),
            finding(package="high-exploit", severity="HIGH", exploit_available=True),
            finding(package="critical", severity="CRITICAL"),
            finding(package="high-epss", severity="HIGH", epss=0.5),
        ]
    )

    assert [g.package for g in groups] == [
        "critical",
        "high-exploit",
        "high-epss",
        "high",
        "low-many",
    ]


def test_keeps_two_copies_of_a_package_apart():
    groups = group_by_package(
        [
            finding(package="glob", file_path="/app/node_modules/glob/package.json"),
            finding(
                package="glob",
                vuln="CVE-2",
                file_path="/usr/local/lib/node_modules/npm/node_modules/glob/package.json",
            ),
        ]
    )

    assert sorted(g.source for g in groups) == [Source.APPLICATION, Source.BASE_IMAGE]

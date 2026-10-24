"""Required named passes and zero skipped tests, matching the Go gate."""
import pytest

REQUIRED = {
    "test_shared_json_conformance", "test_shared_variant_conformance",
    "test_go_numeric_differential", "test_member_and_byte_boundaries",
    "test_offline_registry_resolves_all_bundled_refs",
    "test_wheel_and_sdist_preserve_exact_offline_bundle",
    "test_schema_checkout_bytes_are_portable",
}
PASSED = set()
SKIPPED = []


def pytest_runtest_logreport(report):
    if report.skipped:
        SKIPPED.append(report.nodeid)
    if report.when == "call" and report.passed:
        PASSED.add(report.nodeid.split("::")[-1])


def pytest_sessionfinish(session, exitstatus):
    missing = REQUIRED - PASSED
    if missing or SKIPPED:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        reporter.write_line(f"Foundation gate failed: missing={sorted(missing)}, skipped={SKIPPED}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED

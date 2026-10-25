"""Required named passes and zero skipped tests, matching the Go gate."""
import os

import pytest

REQUIRED = {
    "test_shared_json_conformance", "test_shared_variant_conformance",
    "test_go_numeric_differential", "test_member_and_byte_boundaries",
    "test_offline_registry_resolves_all_bundled_refs",
    "test_shared_image_reference_schema",
    "test_wheel_and_sdist_preserve_exact_offline_bundle",
    "test_schema_checkout_bytes_are_portable",
}
REQUIRED |= {
    "test_shared_directory_rules", "test_private_content_metadata",
    "test_go_casefold_differential", "test_directory_loading",
    "test_directory_limits", "test_directory_changed_file", "test_shared_directory_access",
    "test_windows_root_share_contract", "test_directory_corpus_guards",
}
if os.name == "nt":
    REQUIRED |= {"test_windows_directory_acl", "test_windows_directory_io", "test_windows_directory_cleanup"}
else:
    REQUIRED |= {"test_posix_directory_races", "test_posix_directory_ancestor_replacement",
                 "test_posix_directory_streams",
                 "test_posix_directory_fd_bound", "test_posix_directory_fifo_swap"}
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

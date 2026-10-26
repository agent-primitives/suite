"""Required named passes and zero skipped tests, matching the Go gate."""
import os

import pytest

REQUIRED = {
    "test_shared_json_conformance", "test_shared_variant_conformance",
    "test_go_numeric_differential", "test_member_and_byte_boundaries",
    "test_offline_registry_resolves_all_bundled_refs",
    "test_shared_image_reference_schema", "test_shared_string_length_cases", "test_shared_document_shape_cases",
    "test_wheel_and_sdist_preserve_exact_offline_bundle",
    "test_schema_checkout_bytes_are_portable",
}
REQUIRED |= {
    "test_shared_directory_rules", "test_private_content_metadata",
    "test_go_casefold_differential", "test_directory_loading",
    "test_directory_limits", "test_directory_changed_file", "test_shared_directory_access",
    "test_windows_root_share_contract", "test_directory_corpus_guards",
}
REQUIRED |= {
    "test_shared_archive_cases", "test_go_archive_differential", "test_archive_limits",
    "test_archive_streaming_and_retention", "test_archive_does_not_extract",
    "test_archive_corpus_guards", "test_pax_linear_work", "test_sparse_map_linear_work",
}
REQUIRED |= {"test_shared_oci_cases", "test_oci_corpus_guards", "test_go_oci_differential",
             "test_oci_native_io", "test_oci_stream_bounds", "test_oci_reparse_types", "test_oci_empty_root"}
if os.name == "nt":
    REQUIRED |= {"test_oci_windows_io"}
    REQUIRED |= {"test_windows_directory_acl", "test_windows_directory_io", "test_windows_directory_cleanup"}
else:
    REQUIRED |= {"test_oci_posix_special_files"}
    REQUIRED |= {"test_posix_directory_races", "test_posix_directory_ancestor_replacement",
                 "test_posix_directory_streams",
                 "test_posix_directory_fd_bound", "test_posix_directory_fifo_swap"}
REQUIRED |= {
    "test_shared_declaration_cases", "test_typed_suite_references_are_frozen_and_located",
    "test_existing_shared_shape_and_string_vectors_through_decoder",
    "test_private_document_pipeline_native_directory_and_oci",
    "test_literal_pins_never_parse_or_require_retained_body",
    "test_noncanonical_root_but_canonical_pinned_children",
    "test_repeated_raw_manifest_checks_are_collection_local",
    "test_remote_secret_key_diagnostic_points_to_key",
}
REQUIRED |= {
    f"test_optional_manifest_pins_require_canonical_object_bytes[{bad}-{target}]"
    for bad in (False, True) for target in ("policy", "evals")
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

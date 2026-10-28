"""Required named passes and zero skipped tests, matching the Go gate."""
import json
import os
from pathlib import Path

import pytest

REQUIRED = {
    "test_shared_json_conformance", "test_shared_variant_conformance",
    "test_go_numeric_differential", "test_member_and_byte_boundaries",
    "test_offline_registry_resolves_all_bundled_refs",
    "test_shared_image_reference_schema", "test_shared_string_length_cases", "test_shared_document_shape_cases",
    "test_shared_catalog_reference_cases",
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
REQUIRED |= {
    "test_shared_bundle_cases", "test_private_variant_inventory_and_directory_modes",
    "test_bundled_native_directory_and_archive_authority",
    "test_directory_mode_binding_does_not_rewrite_archive_or_allow_conflicts",
    "test_all_variants_bind_directory_modes_even_if_not_selected",
    "test_dependency_closure_exact_order_cycles_and_deep_chain",
    "test_dependency_edge_is_checked_before_visited_reuse",
    "test_collision_equality_ignores_path_and_component_but_not_metadata",
}
REQUIRED |= {
    "test_shared_graph_cases", "test_private_graph_minimal_and_original_bytes",
    "test_repeated_graph_manifests_are_decoded_once_per_call",
    "test_graph_native_directory_and_oci", "test_schema_valid_duplicate_execution_fields",
    "test_schema_valid_duplicate_image_platform", "test_image_semantics_after_owning_schema",
    "test_schema_valid_trailing_newline_profile_values",
    "test_schema_valid_duplicate_graph_selection_keys[buildProfiles-minimal]",
    "test_schema_valid_duplicate_graph_selection_keys[compositions-minimal]",
    "test_schema_valid_duplicate_graph_selection_keys[runtimeProfiles-runtime-two-profiles]",
    "test_schema_valid_duplicate_graph_selection_keys[toolProviderCompositions-standalone]",
}
REQUIRED |= {
    'test_json_uniqueness_matches_stock_equality_and_diagnostics',
    'test_non_json_values_keep_stock_fallback',
    'test_nested_array_sorting_keeps_stock_acceptance',
    'test_disabled_and_non_array_uniqueness_keep_stock',
    'test_comparison_counter_observes_stock_all_pairs',
    'test_wide_resolved_provider_objects_keep_schema_uniqueness',
    'test_schema_views_preserve_original_resources_and_self_references',
    'test_dynamic_anchor_rebinding_keeps_stock_diagnostics',
    'test_mixed_and_nested_dialects_keep_stock_semantics',
    'test_pointer_to_foreign_dialect_in_unknown_keyword_keeps_stock',
    'test_reference_to_schema_metadata_preserves_previous_behavior',
}
REQUIRED |= {f'test_wide_valid_execution_uniqueness_work[{size}]' for size in (256,512,1024,2048)}
REQUIRED |= {f'test_unique_items_reference_diagnostics_and_work[{ref}]' for ref in ('$ref', '$dynamicRef')}
REQUIRED |= {f'test_shared_composition_provider_presence[{case}]' for case in ('empty', 'omitted', 'null')}
REQUIRED |= {
    'test_small_spool_and_aggregate_rollover',
    'test_reused_metadata_and_empty_literal_need_no_spool',
    'test_large_literal_is_not_a_json_document_limit',
    'test_literal_text_is_incremental_and_bytes_are_authoritative',
    'test_literals_interleave_and_read_concurrently',
    'test_literal_close_and_seal_are_explicit',
    'test_short_spool_writes_are_completed_and_disk_full_propagates',
    'test_shared_literal_capture_cases',
    'test_captured_literals_outlive_oci_layout',
    'test_retained_tool_schema_is_original_not_reread',
    'test_directory_capture_checks_opened_kind_not_only_inode',
    'test_oci_snapshot_disk_full_is_io_failure_and_cleans_up',
    'test_shared_policy_accepted_and_v2_refused_wire_vectors',
    'test_private_policy_records_are_frozen_located_and_keep_raw_bytes',
    'test_evaluation_assertions_preserve_every_operand_and_optional_presence',
    'test_existing_rich_evaluation_fixtures_through_private_decoder',
}
REQUIRED |= {f'test_capture_failure_closes_native_source_handles[{cancel}]' for cancel in ('False','True')}
REQUIRED |= {f'test_captured_go_fixture_literals_outlive_directory[{name}]'
             for name in ('minimal','remote','bundled','runtime-two-profiles')}
REQUIRED |= {f'test_close_releases_reused_payload_even_with_suspended_iterator[{active}]'
             for active in ('False','True')}
REQUIRED |= {
    'test_reader_corpus_guards', 'test_shared_regex_cases', 'test_go_regex_differential',
    'test_native_regex_budget_and_cache_isolation', 'test_native_regex_parse_certificate',
    'test_native_regex_compiles_bounded_syntax', 'test_native_regex_peak_memory',
    'test_native_regex_bounded_range_cpu',
    'test_shared_policy_all_wire_vectors', 'test_package_rich_ordered_authored_views_and_identity',
    'test_package_validate_rehashes_retained_literal_backing',
    'test_package_repr_and_equality_do_not_traverse_captured_content',
    'test_package_construction_failure_releases_captured_snapshot',
    'test_package_context_failure_closes_snapshot_and_discards_private_content',
    'test_package_empty_pathlike_refused_from_valid_package_directory',
    'test_package_marker_io_error_does_not_fall_back_to_directory',
    'test_package_root_can_be_noncanonical_but_pins_stay_verified',
    'test_package_tool_schemas_and_policy_identity_survive_removal',
    'test_unknown_noncritical_value_has_same_schema_flavor',
    'test_foreign_and_mixed_bundles_keep_stock_pattern_semantics',
}
CORPUS = Path(__file__).resolve().parents[2] / 'testdata/conformance'
for filename in ('reader-cases.json', 'reader-semantic-cases.json'):
    for case in json.loads((CORPUS / filename).read_bytes())['cases']:
        REQUIRED.add(f"test_shared_reader_cases[{case['name']}]")
        if case['valid']:
            REQUIRED.add(f"test_shared_reader_oci_positives[{case['name']}]")
for case in json.loads((CORPUS / 'reader-boundary-cases.json').read_bytes())['cases']:
    REQUIRED.add(f"test_shared_reader_boundary_cases[{case['name']}]")
    if os.name != 'nt' and case['name'].startswith('policy-symlink-'):
        REQUIRED.add(f"test_shared_reader_boundary_native_symlinks[{case['name']}]")
for case in json.loads((CORPUS / 'literal-cases.json').read_bytes())['cases']:
    for oci in ('False', 'True'):
        REQUIRED.add(f"test_package_shared_literal_bytes_outlive_source[{case['name']}-{oci}]")
REQUIRED |= {
    'test_public_identity_domains', 'test_instruction_edit_copy_on_write_and_rollback',
    'test_stale_graph_is_never_repaired', 'test_unchanged_oci_preserves_noncanonical_manifest_bytes',
    'test_edit_shared_agent_and_provider_literal_aliases', 'test_edit_failure_transaction_and_stale_old_handles',
    'test_write_cached_metadata_and_literals_ignore_changed_source',
    'test_source_oci_changed_is_refused_without_affecting_reader', 'test_writer_mode_authority_and_links',
    'test_writer_dest_symlink_and_parent_alias_are_refused', 'test_writer_long_pax_paths_and_safe_hardlinks',
    'test_edit_preserves_authored_presence_and_unrelated_raw_documents',
    'test_shared_write_case_population', 'test_write_all_shared_reader_positives',
    'test_instruction_copy_on_write_avoids_folded_name_collisions',
    'test_instruction_copy_on_write_reserves_implicit_directories[False]',
    'test_instruction_copy_on_write_reserves_implicit_directories[True]',
    'test_windows_directory_basename_validation[D:payload.bin]',
    'test_windows_directory_basename_validation[folder/name:stream]',
    'test_windows_directory_basename_validation[folder/CON]',
}
for method in ('write_directory', 'write_oci'):
    REQUIRED.add(f'test_write_closed_and_existing_destination[{method}]')
    for name in ('minimal', 'remote', 'bundled', 'runtime-two-profiles', 'rich'):
        REQUIRED.add(f'test_write_roundtrip_and_repeat[{method}-{name}]')
for flag in ('False', 'True'):
    REQUIRED.add(f'test_missing_or_changed_arbitrary_payload_refused_and_cleaned[{flag}]')
    REQUIRED.add(f'test_writer_missing_payload_above_json_bound[{flag}]')
for failure in ('short', 'zero', 'none', 'io'):
    REQUIRED.add(f'test_write_short_writes_complete_or_clean_up[{failure}]')
for case in json.loads((CORPUS/'literal-cases.json').read_bytes())['cases']:
    REQUIRED.add(f"test_writer_large_and_non_utf8_literals_outlive_source[{case['name']}]")
for name in ('remote', 'bundled', 'runtime-two-profiles'):
    REQUIRED.add(f'test_go_writer_variant_payloads[{name}]')
for case in json.loads((CORPUS/'write-cases.json').read_bytes())['cases']:
    REQUIRED.add(f"test_shared_write_identities_and_go_outputs[{case['name']}]")
REQUIRED |= {
    'test_edit_checks_aggregate_bounds_after_repin_and_rolls_back[regular]',
    'test_edit_checks_aggregate_bounds_after_repin_and_rolls_back[retained]',
    'test_edit_committed_state_survives_old_spool_close_error',
    'test_failed_history_edit_keeps_content_snapshot_and_owned_paths',
    'test_fixed_gzip_store_block_boundaries[131070]',
    'test_fixed_gzip_store_block_boundaries[65534]',
    'test_fixed_gzip_store_block_boundaries[65535]',
    'test_fixed_gzip_store_block_boundaries[65536]',
    'test_fixed_gzip_store_large_sha_and_partitioning[131072]',
    'test_fixed_gzip_store_large_sha_and_partitioning[17408]',
    'test_fixed_gzip_store_large_sha_and_partitioning[3145728]',
    'test_fixed_gzip_store_small_goldens[-1f8b08000000000000ff010000ffff0000000000000000]',
    'test_fixed_gzip_store_small_goldens[abc-1f8b08000000000000ff010300fcff616263c241243503000000]',
    'test_repeated_edits_bound_created_history_and_preserve_original_files',
    'test_writer_cleanup_after_final_modes_preserves_original_error',
    'test_writer_cleanup_removes_readonly_files',
    'test_writer_dotdot_destination_resolves_checked_parent[write_directory]',
    'test_writer_dotdot_destination_resolves_checked_parent[write_oci]',
    'test_writer_new_root_passes_native_security_checks',
    'test_writer_retains_output_descriptors_until_completion',
    'test_writer_readonly_inventory_directory_with_link',
}
REQUIRED |= {
    "test_registry_auth_replay_rewinds_body",
    "test_registry_basic_and_bearer_credentials_are_origin_bound[basic]",
    "test_registry_basic_and_bearer_credentials_are_origin_bound[bearer]",
    "test_registry_bearer_realm_does_not_inherit_registry_password",
    "test_registry_does_not_discover_netrc_or_cookies",
    "test_registry_errors_and_repr_redact_secrets",
    "test_registry_invalid_origins_refuse[]",
    "test_registry_invalid_origins_refuse[file:///path]",
    "test_registry_invalid_origins_refuse[https://fixture:password@registry.test]",
    "test_registry_invalid_origins_refuse[https://registry.test/path]",
    "test_registry_invalid_origins_refuse[https://registry.test?secret=query]",
    "test_registry_malformed_challenges_refuse_safely[Bearer realm=\"ftp://invalid.test/token\"]",
    "test_registry_malformed_challenges_refuse_safely[Bearer realm=\"{base}/token\",broken]",
    "test_registry_malformed_challenges_refuse_safely[Bearer realm=\"{base}/token\",realm=\"{base}/other\"]",
    "test_registry_malformed_challenges_refuse_safely[Bearer service=\"fixture\"]",
    "test_registry_malformed_challenges_refuse_safely[Unknown realm=\"fixture\"]",
    "test_registry_malformed_tokens_refuse_safely[[]]",
    "test_registry_malformed_tokens_refuse_safely[not-json]",
    "test_registry_malformed_tokens_refuse_safely[{\"token\":\"bad token\"}]",
    "test_registry_malformed_tokens_refuse_safely[{\"token\":null}]",
    "test_registry_malformed_tokens_refuse_safely[{}]",
    "test_registry_publish_preserves_manifest_and_blobs",
    "test_registry_refuses_before_network_on_invalid_or_changed_layout[corrupt]",
    "test_registry_refuses_before_network_on_invalid_or_changed_layout[directory]",
    "test_registry_releases_streams_and_session[False]",
    "test_registry_releases_streams_and_session[True]",
    "test_registry_repeat_push_and_missing_optional_headers",
    "test_registry_snapshot_rechecks_bytes_before_http",
    "test_registry_snapshots_outlive_source",
    "test_registry_uncertain_or_mismatched_remote_never_returns_reference[digest-header]",
    "test_registry_uncertain_or_mismatched_remote_never_returns_reference[final-response]",
    "test_registry_uncertain_or_mismatched_remote_never_returns_reference[head-size]",
    "test_registry_uncertain_or_mismatched_remote_never_returns_reference[manifest-digest]",
    "test_registry_upload_queries_and_redirects_preserve_bytes",
    "test_registry_validates_target_and_closes_resources[../suite]",
    "test_registry_validates_target_and_closes_resources[Team/suite]",
    "test_registry_validates_target_and_closes_resources[]",
    "test_registry_validates_target_and_closes_resources[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]",
    "test_registry_validates_target_and_closes_resources[team//suite]",
    "test_registry_validates_target_and_closes_resources[team/suite:tag]",
}
REQUIRED.add('test_registry_selects_bearer_from_multiple_challenges')
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

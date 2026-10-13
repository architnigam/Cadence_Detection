# Extraction test coverage

Run: `python -m unittest discover -s tests/extraction -v`. Set `CADENCE_TEST_REAL_OCR=1` and configure the local engine/model to enable real-engine tests. The test extra in pyproject.toml contains fixture-building dependencies.

Synthetic tests use temporary documents and a controlled OCR stub to test routing, source locations, failure propagation and coordinates. Real-engine tests separately verify actual text recognition, SVG conversion and all five supplied EMFs. These test outputs are not PII-accuracy or structure-preservation scores.

| Area | Cases |
|---|---|
| Validation | Missing/empty/unreadable files, corrupt/signature-mismatched formats, extension case, file/ZIP/page/pixel limits, duplicate members, entity/path traversal protections |
| Word | Paragraph/table order, grid locations, nested/merged tables, Unicode/tabs/breaks, headers/footers, text boxes, comments/footnotes/endnotes, field instructions, metadata, hidden/deleted content, repeated images |
| PowerPoint | Slide order, speaker notes, opt-out, groups/transforms, hidden slides, tables, picture positions, missing relationships |
| PDF | Native/scanned/mixed, multiple pages, password handling, rotation, annotations, attachments, blank pages, image limits, detailed crop mapping and invalid crop definitions |
| OCR/media | Headered/headerless TSV, malformed/nonfinite values, confidence, word offsets, alpha, pixel/upscale mapping, corrupt/multiframe/vector content, SVG resource rejection, missing/failed engine and missing model |
| Contract/CLI | Stable IDs/order, JSON, raw-output generation, exit statuses and failure handling without raw error leakage |

## Individual automated cases

### test_extraction.py

- `test_missing_file`
- `test_directory`
- `test_empty_file`
- `test_unsupported_extension`
- `test_wrong_pdf_signature`
- `test_corrupt_office_package`
- `test_mismatched_office_extension`
- `test_uppercase_extension`
- `test_file_size_limit`
- `test_unreadable_input`
- `test_zip_expansion_limit`
- `test_zip_entry_limit`
- `test_duplicate_zip_members`
- `test_xxe_xml_rejected`
- `test_invalid_options`
- `test_docx_paragraph_table_order`
- `test_table_coordinates`
- `test_docx_no_invented_page_number`
- `test_unicode_tabs_and_breaks_preserved`
- `test_header_footer`
- `test_nested_table`
- `test_horizontal_merge_grid_column`
- `test_textbox_not_duplicated_or_dropped`
- `test_footnotes_comments_endnotes`
- `test_hidden_and_tracked_content_flagged`
- `test_field_instructions_recovered`
- `test_tracked_deletion_requires_review`
- `test_internal_relationship_path_traversal_rejected`
- `test_external_hyperlink_value_recovered`
- `test_metadata_extract_and_skip`
- `test_docx_picture_ocr_and_provenance`
- `test_repeated_picture_occurrences_retained`
- `test_unplaced_unsupported_media_quarantined`
- `test_external_image_not_fetched`
- `test_pptx_slide_order_and_notes`
- `test_pptx_notes_optout_quarantines`
- `test_pptx_table`
- `test_pptx_group`
- `test_pptx_picture_position_mapping`
- `test_pptx_hidden_slide_included`
- `test_pptx_unit_limit`
- `test_rotated_group_flagged`
- `test_missing_slide_relationship_does_not_drop_other_slide`
- `test_native_pdf_and_boxes`
- `test_scanned_pdf_uses_ocr`
- `test_mixed_pdf_keeps_native_and_image_text`
- `test_pdf_page_order`
- `test_pdf_page_limit`
- `test_ocr_detail_crop_and_source_mapping`
- `test_invalid_crop_configuration`
- `test_nonexistent_crop_page_flagged`
- `test_pdf_pixel_limit`
- `test_pdf_encrypted_password`
- `test_pdf_annotation_flagged`
- `test_pdf_attachment_flagged`
- `test_native_pdf_metadata_optout_flagged`
- `test_blank_pdf_not_safe_success`
- `test_rotated_scan`
- `test_ocr_failure_retains_native_text`
- `test_low_ocr_confidence_quarantines_all_blocks`
- `test_no_ocr_engine`
- `test_empty_ocr_on_nonblank_image`
- `test_json_schema_stable_ids_and_order`
- `test_cli_exit_code_and_raw_json`
- `test_tsv_hierarchy_and_confidence`
- `test_bad_tsv_rows_ignored`
- `test_nonfinite_tsv_coordinates_rejected`
- `test_tesseract_js_headerless_tsv`
- `test_svg_external_reference_rejected`
- `test_svg_doctype_rejected`
- `test_svg_css_import_rejected`
- `test_image_upscale_boxes_map_back`
- `test_image_missing_engine`
- `test_corrupt_emf_is_explicitly_rejected`
- `test_corrupt_image`
- `test_image_pixel_limit`
- `test_alpha_composited_on_white`
- `test_multiframe_is_explicitly_flagged`
- `test_tesseract_missing_engine`
- `test_node_missing_model`

### test_real_ocr.py

- `test_real_local_engine_reads_synthetic_text`
- `test_local_svg_converter`
- `test_supplied_metafiles_local_conversion`

Total discovered cases: 83. Real-engine/source cases can skip when their explicit prerequisites are absent.

## Limits

Additional manual evaluation is required for semantic reading order, dense scanned table reconstruction, physical image skew/orientation, image-only photos/signatures, and arbitrary unsupported Office/PDF features. These are surfaced as review requirements rather than a claim that every possible document has been tested.

# Raw-data archive manifest

The five canonical panels and all raw vendor captures are deliberately excluded from Git. `datasets_manifest.csv` and `datasets_manifest.json` record their identity, date coverage, sources, row counts, Solana deployment, and checksums. `asset_metadata/` contains the original small metadata, audit and scale-check outputs.

## Storage and restore

The durable shared-storage URI is not yet supplied. Each manifest row therefore uses an explicit `TBD_SHARED_STORAGE/...` placeholder. Before deleting any local source copy:

1. copy the complete asset directory—including raw source files, canonical panel, metadata and audit—to approved shared storage;
2. replace the placeholder with the durable URI and record access ownership;
3. restore `canonical_panel_5m.csv` to the asset's sanitized export directory;
4. run `Get-FileHash -Algorithm SHA256 <file>` on Windows or `sha256sum <file>` on Unix;
5. compare the result with both `dataset_sha256` and `canonical_file_sha256` in the manifest;
6. verify `asset_metadata.json` against `metadata_sha256`;
7. run the relevant evaluation with the matching `asset_id` and dataset hash.

Null values are intentional where the source material did not provide a version or independent dataset-vs-canonical hash. In the supplied pipeline, `dataset_sha256` is the SHA-256 of `canonical_panel_5m.csv`, so the two values are equal.

`excluded_raw_files.txt` lists excluded file classes and local source locations. It contains inventory only, never credentials.

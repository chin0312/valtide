# Raw-data archive manifest

The five canonical panels and raw vendor captures are not committed. The JSON/CSV manifests record each asset's identity, Solana `chainIndex=501` deployment, date coverage, row/observation counts, and declared checksums. `asset_metadata/` contains compact metadata, audits, scale checks, and a dataset-hash sidecar. The handoff verifier cross-checks these committed records, including SHA-256 of each committed `asset_metadata.json` file.

The metadata-file checksum verifies the committed metadata bytes; it does not prove that the metadata came from a particular original vendor response. Likewise, a declared `dataset_sha256` is not re-computed until the canonical panel is restored. No canonical CSV is in this Git handoff or required by CI.

## Shared-storage handoff checklist

All five `storage_location` values are still `TBD_SHARED_STORAGE/...`. The owner, access policy, and durable shared-storage URIs remain external deliverables; do not invent or substitute local machine paths.

- [ ] Select approved shared storage and record an accountable owner and read-access procedure.
- [ ] Copy each complete asset bundle: raw source captures, selected-deployment record, canonical panel, metadata, audit, and scale-check output.
- [ ] Replace each placeholder only after the copy is durable and accessible to the research owner.
- [ ] Restore the canonical panel and run `sha256sum canonical_panel_5m.csv` (or `Get-FileHash -Algorithm SHA256`); compare against `dataset_sha256` and `canonical_file_sha256`.
- [ ] Hash the restored `asset_metadata.json` and compare against `metadata_sha256`; verify asset, chain, token address, timestamps, and counts.
- [ ] Retain the original fit/calibration inputs and run manifests that bind dataset hash, code revision, parameters, training cutoff, and calibration chronology.
- [ ] Re-run evaluation only with the matching asset identity and exact dataset hash; preserve current inspected windows as development evidence, not a fresh holdout.

The committed manifest currently has matching dataset and canonical-file hash declarations for each asset. The hashes and row/count identities are internally consistent with committed metadata/audit files. Because the source panels are absent, this is consistency verification—not independent recomputation of the market-data checksums or proof of model-training lineage.

`excluded_raw_files.txt` is an inventory of omitted file classes and source locations, not a credential store. Never commit `.Renviron`, credentials, raw response archives, canonical panels, or fitted fold objects.

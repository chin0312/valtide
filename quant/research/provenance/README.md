# Data provenance evidence

`data_pipeline/` is the supplied source used to discover Solana xStock deployments, retrieve OKX OnchainOS and Alpaca observations, build canonical five-minute panels, and emit dataset hashes/audits. It is retained for reproducibility.

No `.Renviron`, credentials, raw HTTP responses, raw observations, canonical panels, local R libraries, or download logs are included. The manifest under `../../data_manifest/` records the outputs and hashes produced by this pipeline.

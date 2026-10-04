# P1a-C runtime snapshot

This is a compatibility-preserving snapshot of `valtide-quant-service-p1ac` arranged into explicit handoff layers:

- `code/`: installable Python package and embedded artifacts used by `from_default_artifacts()`;
- `params/`: canonical fitted P1a parameters;
- `calibration/`: canonical P1a-C calibrator;
- `metadata/`: provenance and asset/dataset binding;
- `tests/`: deterministic inference, schema, identity, and hash checks.

The copies in `params/` and `calibration/` are canonical handoff files. The embedded copies under `code/src/.../model_artifacts/` are byte-identical so the current package import path keeps working.

From this directory:

```bash
python verify_runtime.py
python run_deterministic_tests.py
python -m pytest -q tests
```

The first two commands use only the Python standard library. The pytest command is optional and exercises the same checks through the conventional test runner.

To install the package snapshot:

```bash
python -m pip install -e code
```

This artifact is approved only for NVDAx. An asset or dataset identity mismatch is a hard failure.

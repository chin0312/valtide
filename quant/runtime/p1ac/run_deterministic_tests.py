from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "code" / "src"))
sys.path.insert(0, str(ROOT))


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    failures = []
    count = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        module = load_module(path)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            count += 1
            try:
                function()
            except Exception as exc:  # noqa: BLE001 - compact local test runner
                failures.append(f"{path.name}::{name}: {type(exc).__name__}: {exc}")
    if failures:
        raise SystemExit("\n".join([f"{len(failures)}/{count} tests failed", *failures]))
    print(f"{count} deterministic runtime tests passed")


if __name__ == "__main__":
    main()

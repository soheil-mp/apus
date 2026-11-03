#!/usr/bin/env python3
"""Generate Python code from the Protobuf schemas in ``proto/``.

The code goes to ``packages/apus-core/src/apus_core/gen/`` and is committed, so the packages
install without a Protobuf compiler. ``protoc`` comes from the ``grpcio-tools`` development
dependency, which bundles it.

Usage::

    uv run python scripts/gen_proto.py          # regenerate
    uv run python scripts/gen_proto.py --check  # fail if the committed code is out of date
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = ROOT / "proto"
GEN_DIR = ROOT / "packages" / "apus-core" / "src" / "apus_core" / "gen"
INIT_TEXT = '"""Generated from the Protobuf schemas in proto/ by scripts/gen_proto.py."""\n'


def generate(out_dir: Path) -> list[Path]:
    """Run ``protoc`` for every schema into ``out_dir``; returns the files written."""
    from grpc_tools import protoc  # noqa: PLC0415 - development dependency only

    schemas = sorted(PROTO_DIR.rglob("*.proto"))
    include = Path(protoc.__file__).parent / "_proto"
    args = [
        "protoc",
        f"-I{PROTO_DIR}",
        f"-I{include}",
        f"--python_out={out_dir}",
        f"--pyi_out={out_dir}",
        *(str(s) for s in schemas),
    ]
    if protoc.main(args) != 0:
        msg = "protoc failed"
        raise RuntimeError(msg)
    for package_dir in [out_dir, *(p for p in out_dir.rglob("*") if p.is_dir())]:
        (package_dir / "__init__.py").write_text(INIT_TEXT, encoding="utf-8")
    return sorted(p for p in out_dir.rglob("*") if p.is_file())


def differences(expected_dir: Path, actual_dir: Path) -> list[str]:
    """Relative paths that differ between two generated trees."""
    expected = {p.relative_to(expected_dir) for p in expected_dir.rglob("*") if p.is_file()}
    actual = {p.relative_to(actual_dir) for p in actual_dir.rglob("*") if p.is_file()}
    actual = {p for p in actual if "__pycache__" not in p.parts}
    changed = [
        p
        for p in expected & actual
        if not filecmp.cmp(expected_dir / p, actual_dir / p, shallow=False)
    ]
    return sorted(str(p) for p in (expected ^ actual) | set(changed))


def main(argv: list[str] | None = None) -> int:
    """Regenerate the code, or check that it is current with ``--check``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check, change nothing")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        generate(fresh)
        stale = differences(fresh, GEN_DIR) if GEN_DIR.exists() else ["(missing)"]
        if args.check:
            if stale:
                print("Generated Protobuf code is out of date:", *stale, sep="\n  ")
                print("Run: uv run python scripts/gen_proto.py")
                return 1
            print("Generated Protobuf code is current.")
            return 0
        shutil.rmtree(GEN_DIR, ignore_errors=True)
        shutil.copytree(fresh, GEN_DIR)
    print(f"Wrote {GEN_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

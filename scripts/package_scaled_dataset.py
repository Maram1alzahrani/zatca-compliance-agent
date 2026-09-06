#!/usr/bin/env python3
"""Create a deterministic ZIP release of synthetic dataset v1."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_OUTPUT = DEFAULT_DATA_ROOT / "releases" / "zatca_synthetic_v1.zip"
FIXED_TIMESTAMP = (2026, 9, 6, 0, 0, 0)


def package(data_root: Path, output: Path) -> str:
    roots = (data_root / "synthetic" / "v1", data_root / "ground_truth" / "v1")
    files = sorted(path for root in roots for path in root.rglob("*") if path.is_file())
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = ZipInfo(str(path.relative_to(data_root)).replace("\\", "/"), FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    digest = package(args.data_root, args.output)
    print(f"Created {args.output} sha256={digest}")


if __name__ == "__main__":
    main()

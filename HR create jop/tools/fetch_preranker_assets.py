"""Fetch pinned CPU ranking assets at build time, never at application runtime."""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

REVISION = "ccc66d3bcd826f577e26b9a4072cc5fe3a7ad6a3"
FILES = {
    "model_O4.onnx": (
        "onnx/model_O4.onnx",
        "4654c156f3e4171abc9c716cdb771bf9116455d15ac1aab364aeeede0e3205b0",
    ),
    "tokenizer.json": (
        "onnx/tokenizer.json",
        "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    ),
    "model_qint8_avx512_vnni.onnx": (
        "onnx/model_qint8_avx512_vnni.onnx",
        "dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(name: str, destination: Path) -> None:
    relative, expected = FILES[name]
    if destination.is_file():
        if sha256_file(destination) == expected:
            return
        raise ValueError(
            f"Existing pinned artifact {name} has a checksum mismatch; left unchanged."
        )
    url = f"https://huggingface.co/intfloat/multilingual-e5-small/resolve/{REVISION}/{relative}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with urllib.request.urlopen(url, timeout=60) as response:
                while block := response.read(1024 * 1024):
                    digest.update(block)
                    temporary.write(block)
        if digest.hexdigest() != expected:
            raise ValueError(f"Checksum mismatch for pinned artifact {name}.")
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("models/multilingual-e5-small"))
    parser.add_argument("--include-quantized", action="store_true")
    args = parser.parse_args()
    names = ["model_O4.onnx", "tokenizer.json"]
    if args.include_quantized:
        names.append("model_qint8_avx512_vnni.onnx")
    for name in names:
        download_verified(name, args.output / name)
    print(f"Verified {len(names)} pinned assets at model revision {REVISION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

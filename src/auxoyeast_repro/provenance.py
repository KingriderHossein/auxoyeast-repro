from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import platform
import sys

import cobra
import numpy as np
import pandas as pd

from .config import AuditConfig


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_provenance(input_files: list[Path], config: AuditConfig) -> dict:
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cobra": cobra.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "config": asdict(config),
        "files": {
            path.name: {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in input_files
        },
    }


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

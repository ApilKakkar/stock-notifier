"""Parquet writing (atomic) and the data-lineage manifest."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def update_manifest(data_dir: Path, key: str, entry: dict) -> None:
    """Record what was pulled, from where, when, and how clean it was (data lineage)."""
    path = data_dir / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    entry = {**entry, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    manifest[key] = entry
    data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str))

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    uploads_dir: Path
    max_file_size: int = 20 * 1024 * 1024
    pipeline_version: str = "rules-0.2.0"


def get_settings() -> Settings:
    data_dir = Path(os.getenv("CONTRACT_EXTRACTOR_DATA_DIR", "runtime")).resolve()
    return Settings(
        data_dir=data_dir,
        database_path=data_dir / "contracts.sqlite3",
        uploads_dir=data_dir / "uploads",
    )


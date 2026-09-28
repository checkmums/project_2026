from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "contract_dataset_v2"
ARCHIVE = ROOT / "contract_dataset_v2.zip"

shutil.copy2(ROOT / "baseline_results_v2.csv", DATASET / "baseline_results_v2.csv")
shutil.copy2(ROOT / "PARSER_EVALUATION_V2.md", DATASET / "PARSER_EVALUATION_V2.md")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


files = sorted(path for path in DATASET.rglob("*") if path.is_file() and path.name not in {"checksums.sha256", "labels.xlsx.inspect.ndjson"})
lines = [f"{digest(path)}  {path.relative_to(DATASET)}" for path in files]
(DATASET / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as archive:
    for path in sorted(p for p in DATASET.rglob("*") if p.is_file() and p.name != "labels.xlsx.inspect.ndjson"):
        archive.write(path, Path(DATASET.name) / path.relative_to(DATASET))

print(f"Packaged {len(files)} files into {ARCHIVE}")

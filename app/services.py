from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from app.config import Settings
from app.database import Database
from app.extraction import extract_contract
from app.schemas import DocumentDetail


ALLOWED_FORMATS = {".pdf": "PDF", ".docx": "DOCX"}


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-zА-Яа-яЁё0-9._-]", "_", name)[:180]


def process_upload(
    filename: str,
    content: bytes,
    settings: Settings,
    database: Database,
) -> DocumentDetail:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_FORMATS:
        raise ValueError("Поддерживаются только файлы PDF и DOCX")
    if not content:
        raise ValueError("Загружен пустой файл")
    if len(content) > settings.max_file_size:
        raise ValueError("Размер файла превышает 20 МБ")

    sha256 = hashlib.sha256(content).hexdigest()
    existing_uid = database.find_by_hash(sha256)
    if existing_uid:
        existing = database.get_document(existing_uid, duplicate=True)
        if existing:
            return existing

    uid = str(uuid.uuid4())
    filename = safe_filename(filename)
    storage_name = f"{uid}_{filename}"
    storage_path = settings.uploads_dir / storage_name
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)
    document_id = database.create_document(
        uid, filename, ALLOWED_FORMATS[extension], str(storage_path), sha256
    )
    try:
        result = extract_contract(storage_path, ALLOWED_FORMATS[extension], settings.pipeline_version)
        database.save_extraction(document_id, result)
    except Exception as exc:
        database.mark_error(document_id, str(exc), settings.pipeline_version)
        storage_path.unlink(missing_ok=True)
        raise ValueError(f"Не удалось обработать файл: {exc}") from exc

    detail = database.get_document(uid)
    if detail is None:  # pragma: no cover - database consistency guard
        raise RuntimeError("Результат обработки не сохранён")
    return detail


def reprocess(uid: str, settings: Settings, database: Database) -> DocumentDetail | None:
    record = database.get_storage_record(uid)
    if record is None:
        return None
    result = extract_contract(Path(record["storage_path"]), record["file_format"], settings.pipeline_version)
    database.save_extraction(int(record["id"]), result)
    return database.get_document(uid)


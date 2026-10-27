from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings
from app.database import Database


def test_upload_and_registry(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "test.sqlite3",
        uploads_dir=tmp_path / "uploads",
    )
    database = Database(settings.database_path, Path("tomorrow_demo/schema_v2.sql"))
    main.settings = settings
    main.database = database

    sample = Path("contract_dataset_v2/documents/contract_01.docx")
    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": (sample.name, sample.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["contract_number"] == "101/26"
        assert payload["extraction"]["amount"]["value"] == 75000.0

        registry = client.get("/api/v1/contracts")
        assert registry.status_code == 200
        assert len(registry.json()) == 1


def test_rejects_unsupported_file(tmp_path: Path) -> None:
    settings = Settings(tmp_path, tmp_path / "test.sqlite3", tmp_path / "uploads")
    database = Database(settings.database_path, Path("tomorrow_demo/schema_v2.sql"))
    main.settings = settings
    main.database = database

    with TestClient(main.app) as client:
        response = client.post("/api/v1/documents", files={"file": ("notes.txt", b"text", "text/plain")})
        assert response.status_code == 422


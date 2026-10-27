from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.database import Database
from app.schemas import BatchUploadResponse, DocumentDetail, DocumentSummary, RegistryStats
from app.services import process_upload, reprocess


settings = get_settings()
database = Database(settings.database_path, Path(__file__).parents[1] / "tomorrow_demo" / "schema_v2.sql")


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize()
    yield


app = FastAPI(
    title="Contract Extractor API",
    description=(
        "Промежуточная версия сервиса извлечения реквизитов договоров. "
        "Аутентификация и пользовательский интерфейс запланированы на следующий этап."
    ),
    version=__version__,
    lifespan=lifespan,
)

web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")


@app.get("/", include_in_schema=False)
def web_interface() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "pipeline": settings.pipeline_version}


@app.post(
    "/api/v1/documents",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def upload_document(file: UploadFile = File(...)) -> DocumentDetail:
    try:
        return process_upload(file.filename or "document", await file.read(), settings, database)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/documents/batch", response_model=BatchUploadResponse, tags=["documents"])
async def upload_batch(files: list[UploadFile] = File(...)) -> BatchUploadResponse:
    if not files:
        raise HTTPException(status_code=422, detail="Не выбраны файлы")
    processed: list[DocumentDetail] = []
    errors: list[dict[str, str]] = []
    for file in files:
        try:
            processed.append(process_upload(file.filename or "document", await file.read(), settings, database))
        except ValueError as exc:
            errors.append({"filename": file.filename or "document", "error": str(exc)})
    return BatchUploadResponse(processed=processed, errors=errors)


@app.get("/api/v1/contracts", response_model=list[DocumentSummary], tags=["registry"])
def registry(
    q: str | None = Query(None, description="Номер договора или название стороны"),
    sort_by: str = Query("uploaded_at", pattern="^(uploaded_at|contract_date|amount|contract_number)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> list[DocumentSummary]:
    return database.list_documents(q, sort_by, order)


@app.get("/api/v1/documents/{document_uid}", response_model=DocumentDetail, tags=["documents"])
def document_detail(document_uid: str) -> DocumentDetail:
    document = database.get_document(document_uid)
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return document


@app.post("/api/v1/documents/{document_uid}/reprocess", response_model=DocumentDetail, tags=["documents"])
def reprocess_document(document_uid: str) -> DocumentDetail:
    try:
        document = reprocess(document_uid, settings, database)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return document


@app.delete("/api/v1/documents/{document_uid}", tags=["documents"])
def delete_document(document_uid: str) -> dict[str, str]:
    storage_path = database.delete_document(document_uid)
    if storage_path is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    Path(storage_path).unlink(missing_ok=True)
    return {"status": "deleted", "document_uid": document_uid}


@app.get("/api/v1/stats", response_model=RegistryStats, tags=["registry"])
def stats() -> RegistryStats:
    return RegistryStats.model_validate(database.stats())


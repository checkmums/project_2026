from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.schemas import DocumentDetail, DocumentSummary, ExtractionResult


class Database:
    def __init__(self, path: Path, schema_path: Path) -> None:
        self.path = path
        self.schema_path = schema_path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            schema_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'documents'"
            ).fetchone()
            if not schema_exists:
                connection.executescript(self.schema_path.read_text(encoding="utf-8"))
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS extraction_payloads (
                    document_id INTEGER PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def find_by_hash(self, sha256: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT document_uid FROM documents WHERE sha256 = ?", (sha256,)
            ).fetchone()
        return str(row["document_uid"]) if row else None

    def create_document(
        self, uid: str, filename: str, file_format: str, storage_path: str, sha256: str
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents
                    (document_uid, original_filename, file_format, storage_path, sha256,
                     has_text_layer, processing_status)
                VALUES (?, ?, ?, ?, ?, NULL, 'processing')
                """,
                (uid, filename, file_format, storage_path, sha256),
            )
            return int(cursor.lastrowid)

    def mark_error(self, document_id: int, message: str, pipeline_version: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE documents SET processing_status = 'error', has_text_layer = 0 WHERE id = ?",
                (document_id,),
            )
            connection.execute(
                """
                INSERT INTO processing_runs
                    (document_id, pipeline_version, extraction_model, finished_at, status, error_message)
                VALUES (?, ?, 'regex-context', CURRENT_TIMESTAMP, 'error', ?)
                """,
                (document_id, pipeline_version, message),
            )

    def save_extraction(self, document_id: int, result: ExtractionResult) -> None:
        statuses = [
            result.contract_number.status,
            result.contract_date.status,
            result.customer.status,
            result.contractor.status,
            result.amount.status,
        ]
        document_status = "processed" if all(status == "found" for status in statuses) else "needs_review"
        with self.connect() as connection:
            run = connection.execute(
                """
                INSERT INTO processing_runs
                    (document_id, pipeline_version, extraction_model, finished_at, status)
                VALUES (?, ?, 'regex-context', CURRENT_TIMESTAMP, 'success')
                """,
                (document_id, result.pipeline_version),
            )
            run_id = int(run.lastrowid)
            connection.execute("DELETE FROM contracts WHERE document_id = ?", (document_id,))
            contract = connection.execute(
                """
                INSERT INTO contracts
                    (document_id, contract_number, contract_date, amount, currency)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    result.contract_number.value,
                    result.contract_date.value,
                    result.amount.value,
                    result.currency or "RUB",
                ),
            )
            contract_id = int(contract.lastrowid)

            for field_name, field in (
                ("contract_number", result.contract_number),
                ("contract_date", result.contract_date),
                ("customer", result.customer),
                ("contractor", result.contractor),
                ("amount", result.amount),
            ):
                connection.execute(
                    """
                    INSERT INTO extraction_results
                        (run_id, field_name, raw_value, normalized_value, page_number,
                         source_context, extraction_method, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        field_name,
                        field.raw_value,
                        str(field.value) if field.value is not None else None,
                        field.page_number,
                        field.evidence,
                        field.method,
                        field.confidence,
                    ),
                )

            for role_code, party in (("customer", result.customer), ("contractor", result.contractor)):
                if not party.value:
                    continue
                name = str(party.value)
                party_type = "individual_entrepreneur" if name.startswith("ИП ") else "organization"
                connection.execute(
                    "INSERT OR IGNORE INTO parties (normalized_name, party_type) VALUES (?, ?)",
                    (name, party_type),
                )
                party_id = connection.execute(
                    "SELECT id FROM parties WHERE normalized_name = ?", (name,)
                ).fetchone()["id"]
                connection.execute(
                    """
                    INSERT INTO contract_parties (contract_id, party_id, role_code, role_label)
                    VALUES (?, ?, ?, ?)
                    """,
                    (contract_id, party_id, role_code, party.role_label or role_code),
                )

            payload = result.model_dump_json()
            connection.execute(
                """
                INSERT INTO extraction_payloads (document_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(document_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (document_id, payload),
            )
            connection.execute(
                "UPDATE documents SET processing_status = ?, has_text_layer = 1 WHERE id = ?",
                (document_status, document_id),
            )

    @staticmethod
    def _summary(row: sqlite3.Row) -> DocumentSummary:
        return DocumentSummary(
            document_uid=row["document_uid"],
            filename=row["original_filename"],
            file_format=row["file_format"],
            uploaded_at=row["uploaded_at"],
            processing_status=row["processing_status"],
            contract_number=row["contract_number"],
            contract_date=row["contract_date"],
            customer=row["customer"],
            contractor=row["contractor"],
            amount=float(row["amount"]) if row["amount"] is not None else None,
            currency=row["currency"],
        )

    @staticmethod
    def _registry_sql() -> str:
        return """
            SELECT d.document_uid, d.original_filename, d.file_format, d.uploaded_at,
                   d.processing_status, c.contract_number, c.contract_date, c.amount, c.currency,
                   MAX(CASE WHEN cp.role_code = 'customer' THEN p.normalized_name END) AS customer,
                   MAX(CASE WHEN cp.role_code = 'contractor' THEN p.normalized_name END) AS contractor
            FROM documents d
            LEFT JOIN contracts c ON c.document_id = d.id
            LEFT JOIN contract_parties cp ON cp.contract_id = c.id
            LEFT JOIN parties p ON p.id = cp.party_id
        """

    def list_documents(self, query: str | None, sort_by: str, order: str) -> list[DocumentSummary]:
        sort_columns = {
            "uploaded_at": "d.uploaded_at", "contract_date": "c.contract_date",
            "amount": "c.amount", "contract_number": "c.contract_number",
        }
        sort_column = sort_columns.get(sort_by, "d.uploaded_at")
        direction = "ASC" if order.lower() == "asc" else "DESC"
        params: list[str] = []
        where = ""
        if query:
            where = """
                WHERE c.contract_number LIKE ? OR EXISTS (
                    SELECT 1 FROM contract_parties cp2
                    JOIN parties p2 ON p2.id = cp2.party_id
                    WHERE cp2.contract_id = c.id AND p2.normalized_name LIKE ?
                )
            """
            params.extend([f"%{query}%", f"%{query}%"])
        sql = self._registry_sql() + where + f" GROUP BY d.id ORDER BY {sort_column} {direction}"
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._summary(row) for row in rows]

    def get_document(self, uid: str, duplicate: bool = False) -> DocumentDetail | None:
        sql = self._registry_sql() + " WHERE d.document_uid = ? GROUP BY d.id"
        with self.connect() as connection:
            row = connection.execute(sql, (uid,)).fetchone()
            if not row:
                return None
            payload_row = connection.execute(
                """
                SELECT ep.payload_json FROM extraction_payloads ep
                JOIN documents d ON d.id = ep.document_id
                WHERE d.document_uid = ?
                """,
                (uid,),
            ).fetchone()
        if not payload_row:
            return None
        summary = self._summary(row)
        return DocumentDetail(
            **summary.model_dump(),
            extraction=ExtractionResult.model_validate(json.loads(payload_row["payload_json"])),
            duplicate=duplicate,
        )

    def get_storage_record(self, uid: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT id, storage_path, file_format FROM documents WHERE document_uid = ?", (uid,)
            ).fetchone()

    def delete_document(self, uid: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT storage_path FROM documents WHERE document_uid = ?", (uid,)
            ).fetchone()
            if not row:
                return None
            connection.execute("DELETE FROM documents WHERE document_uid = ?", (uid,))
        return str(row["storage_path"])

    def stats(self) -> dict:
        fields = ["contract_number", "contract_date", "customer", "contractor", "amount"]
        with self.connect() as connection:
            counts = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(processing_status = 'processed') AS processed,
                       SUM(processing_status = 'needs_review') AS needs_review,
                       SUM(processing_status = 'error') AS errors
                FROM documents
                """
            ).fetchone()
            found_share: dict[str, float] = {}
            total = int(counts["total"] or 0)
            for field in fields:
                found = connection.execute(
                    """
                    SELECT COUNT(*) AS count FROM extraction_payloads
                    WHERE json_extract(payload_json, ?) = 'found'
                    """,
                    (f"$.{field}.status",),
                ).fetchone()["count"]
                found_share[field] = round(found / total, 3) if total else 0.0
        return {
            "documents": total,
            "processed": int(counts["processed"] or 0),
            "needs_review": int(counts["needs_review"] or 0),
            "errors": int(counts["errors"] or 0),
            "found_share": found_share,
        }


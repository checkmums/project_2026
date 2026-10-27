from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FieldStatus = Literal["found", "not_found", "needs_review"]


class ExtractedField(BaseModel):
    value: str | float | None = None
    raw_value: str | None = None
    status: FieldStatus = "not_found"
    confidence: float = Field(ge=0, le=1, default=0)
    evidence: str | None = None
    page_number: int | None = None
    paragraph_number: int | None = None
    method: str = "rule"
    reason: str | None = None


class PartyField(ExtractedField):
    role_label: str | None = None


class ExtractionResult(BaseModel):
    contract_number: ExtractedField
    contract_date: ExtractedField
    customer: PartyField
    contractor: PartyField
    amount: ExtractedField
    currency: str | None = None
    pipeline_version: str


class DocumentSummary(BaseModel):
    document_uid: str
    filename: str
    file_format: str
    uploaded_at: str
    processing_status: str
    contract_number: str | None = None
    contract_date: str | None = None
    customer: str | None = None
    contractor: str | None = None
    amount: float | None = None
    currency: str | None = None


class DocumentDetail(DocumentSummary):
    extraction: ExtractionResult
    duplicate: bool = False


class BatchUploadResponse(BaseModel):
    processed: list[DocumentDetail]
    errors: list[dict[str, str]]


class RegistryStats(BaseModel):
    documents: int
    processed: int
    needs_review: int
    errors: int
    found_share: dict[str, float]


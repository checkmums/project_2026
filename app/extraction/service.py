from __future__ import annotations

from pathlib import Path

from app.extraction.ner import extract_named_entities
from app.extraction.readers import read_document
from app.extraction.rules import extract_amount, extract_date, extract_number, extract_parties
from app.schemas import ExtractionResult


def extract_contract(path: Path, file_format: str, pipeline_version: str) -> ExtractionResult:
    chunks = read_document(path, file_format)
    named_entities = extract_named_entities(chunks)
    number = extract_number(chunks)
    contract_date = extract_date(chunks)
    customer, contractor = extract_parties(chunks, named_entities)
    amount, currency = extract_amount(chunks)
    return ExtractionResult(
        contract_number=number,
        contract_date=contract_date,
        customer=customer,
        contractor=contractor,
        amount=amount,
        currency=currency,
        pipeline_version=pipeline_version,
    )


from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from app.extraction.readers import TextChunk
from app.schemas import ExtractedField, PartyField


MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
ENTITY = r"(?:ООО|АО|ПАО|ЗАО|ИП)\s+(?:[«\"].+?[»\"]|[А-ЯЁ][А-Яа-яЁё.-]+(?:\s+[А-ЯЁ][А-Яа-яЁё.-]+){1,3})"
ROLE_MAP = {
    "заказчик": "customer", "покупатель": "customer", "арендатор": "customer",
    "принципал": "customer", "клиент": "customer", "заемщик": "customer",
    "лицензиат": "customer", "поклажедатель": "customer", "страхователь": "customer",
    "исполнитель": "contractor", "поставщик": "contractor", "подрядчик": "contractor",
    "арендодатель": "contractor", "агент": "contractor", "перевозчик": "contractor",
    "хранитель": "contractor", "займодавец": "contractor", "лицензиар": "contractor",
    "страховщик": "contractor",
}


@dataclass(frozen=True)
class Candidate:
    value: str | float
    raw: str
    confidence: float
    chunk: TextChunk
    method: str
    role_label: str | None = None


def _evidence(chunks: list[TextChunk], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(chunks), index + 2)
    return " ".join(chunk.text for chunk in chunks[start:end])[:500]


def _field(candidate: Candidate | None, chunks: list[TextChunk], reason: str | None = None) -> ExtractedField:
    if candidate is None:
        return ExtractedField(reason=reason or "Подходящий кандидат не найден")
    index = chunks.index(candidate.chunk)
    status = "found" if candidate.confidence >= 0.85 else "needs_review"
    return ExtractedField(
        value=candidate.value,
        raw_value=candidate.raw,
        status=status,
        confidence=candidate.confidence,
        evidence=_evidence(chunks, index),
        page_number=candidate.chunk.page_number,
        paragraph_number=candidate.chunk.paragraph_number,
        method=candidate.method,
        reason=None if status == "found" else reason or "Недостаточная уверенность правила",
    )


def extract_number(chunks: list[TextChunk]) -> ExtractedField:
    patterns = [
        re.compile(r"(?:договор(?:а)?\s*)?№\s*([A-ZА-ЯЁ0-9][A-ZА-ЯЁа-яё0-9./_-]{1,30})", re.I),
        re.compile(r"номер\s+(?:договора|документа)\s*(?:[:№|]|\s)\s*([A-ZА-ЯЁ0-9][A-ZА-ЯЁа-яё0-9./_-]{1,30})", re.I),
    ]
    candidates: list[Candidate] = []
    for index, chunk in enumerate(chunks):
        for pattern in patterns:
            match = pattern.search(chunk.text)
            if not match:
                continue
            context = " ".join(c.text for c in chunks[max(0, index - 2):index + 2]).lower()
            confidence = 0.96 if "договор" in context and "приложен" not in context else 0.7
            candidates.append(Candidate(match.group(1).rstrip(".,"), match.group(0), confidence, chunk, "regex:number_anchor"))
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    return _field(candidates[0] if candidates else None, chunks)


def _to_iso(day: str, month: str, year: str) -> str | None:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def extract_date(chunks: list[TextChunk]) -> ExtractedField:
    numeric = re.compile(r"(?<!\d)([0-3]?\d)[./-]([01]?\d)[./-](20\d{2})(?!\d)")
    verbal = re.compile(r"[«\"]?([0-3]?\d)[»\"]?\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})\s*(?:г\.?|года)?", re.I)
    candidates: list[Candidate] = []
    for index, chunk in enumerate(chunks):
        context = " ".join(c.text for c in chunks[max(0, index - 2):index + 2]).lower()
        for match in numeric.finditer(chunk.text):
            value = _to_iso(*match.groups())
            if value:
                score = 0.94 if index < 12 and "договор" in context else 0.72
                candidates.append(Candidate(value, match.group(0), score, chunk, "regex:date"))
        for match in verbal.finditer(chunk.text):
            value = _to_iso(match.group(1), str(MONTHS[match.group(2).lower()]), match.group(3))
            if value:
                score = 0.92 if index < 12 else 0.75
                candidates.append(Candidate(value, match.group(0), score, chunk, "regex:verbal_date"))
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    return _field(candidates[0] if candidates else None, chunks)


def _parse_money(raw: str) -> float | None:
    cleaned = re.sub(r"[\s\u00a0]", "", raw).replace(",", ".")
    if cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        return float(Decimal(cleaned))
    except InvalidOperation:
        return None


def extract_amount(chunks: list[TextChunk]) -> tuple[ExtractedField, str | None]:
    money = re.compile(r"(?<!\d)(\d{1,3}(?:[\s\u00a0.]\d{3})*(?:[,.]\d{2})?|\d{4,})(?!\d)(?:\s*\([^)]{0,60}\))?\s*(руб(?:лей|ля|ль|\.)?|₽|RUB|USD|EUR)", re.I)
    anchors = ("сумма договора", "цена договора", "общая стоимость", "стоимость обязательств", "установлена в размере", "согласована в размере", "составляет")
    reject = ("штраф", "пен", "аванс", "ндс", "цена единицы")
    candidates: list[Candidate] = []
    currency_by_candidate: dict[tuple[str, int], str] = {}
    for index, chunk in enumerate(chunks):
        context = " ".join(c.text for c in chunks[max(0, index - 1):index + 2]).lower()
        for match in money.finditer(chunk.text):
            value = _parse_money(match.group(1))
            if value is None:
                continue
            score = 0.95 if any(anchor in context for anchor in anchors) else 0.63
            if any(word in context for word in reject):
                score -= 0.35
            candidate = Candidate(value, match.group(0), max(0.1, score), chunk, "regex:money_anchor")
            candidates.append(candidate)
            token = match.group(2).upper()
            currency_by_candidate[(candidate.raw, id(candidate.chunk))] = "USD" if token == "USD" else "EUR" if token == "EUR" else "RUB"
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    if not candidates:
        return _field(None, chunks), None
    best = candidates[0]
    high_values = {candidate.value for candidate in candidates if candidate.confidence >= 0.85}
    reason = None
    if len(high_values) > 1:
        best = Candidate(best.value, best.raw, 0.75, best.chunk, best.method)
        reason = "Найдено несколько различных сумм с сильными контекстными признаками"
    return _field(best, chunks, reason), currency_by_candidate.get((best.raw, id(best.chunk)))


def _party(candidate: Candidate | None, chunks: list[TextChunk]) -> PartyField:
    base = _field(candidate, chunks)
    return PartyField(**base.model_dump(), role_label=candidate.role_label if candidate else None)


def extract_parties(chunks: list[TextChunk]) -> tuple[PartyField, PartyField]:
    found: dict[str, list[Candidate]] = {"customer": [], "contractor": []}
    entity_pattern = re.compile(ENTITY)
    role_names = "|".join(ROLE_MAP)
    entity_then_role = re.compile(
        rf"(?P<entity>{ENTITY})[^.;]{{0,100}}?именуем\w*\s+(?:в\s+)?(?:дальнейшем|далее)\s+[«\"]?(?P<role>{role_names})[»\"]?",
        re.I,
    )
    role_then_entity = re.compile(
        rf"[«\"]?(?P<role>{role_names})[»\"]?\)?\s*[:|—-]?\s*(?P<entity>{ENTITY})",
        re.I,
    )

    for index, chunk in enumerate(chunks):
        window = " ".join(item.text for item in chunks[index:index + 2])
        for pattern, method in (
            (entity_then_role, "regex:entity_role_context"),
            (role_then_entity, "regex:role_entity_context"),
        ):
            for match in pattern.finditer(window):
                label = match.group("role")
                entity = match.group("entity").rstrip(".,;")
                key = ROLE_MAP[label.lower()]
                found[key].append(Candidate(entity, entity, 0.94, chunk, method, label.title()))

        normalized_role = chunk.text.strip(" :—-").lower()
        if normalized_role in ROLE_MAP:
            key = ROLE_MAP[normalized_role]
            for next_chunk in chunks[index + 1:index + 3]:
                entities = list(entity_pattern.finditer(next_chunk.text))
                if entities:
                    role_order = [
                        part.strip().lower() for part in re.split(r"[|]", chunk.text)
                        if part.strip().lower() in ROLE_MAP
                    ]
                    entity_index = role_order.index(normalized_role) if normalized_role in role_order and len(entities) > 1 else 0
                    entity = entities[min(entity_index, len(entities) - 1)]
                    entity_value = entity.group(0).rstrip(".,;")
                    found[key].append(Candidate(entity_value, entity_value, 0.91, next_chunk, "regex:role_next_line", chunk.text.strip()))
                    break

    customer = found["customer"][0] if found["customer"] else None
    contractor = found["contractor"][0] if found["contractor"] else None
    if customer and contractor and customer.value == contractor.value:
        contractor = Candidate(contractor.value, contractor.raw, 0.55, contractor.chunk, contractor.method, contractor.role_label)
    return _party(customer, chunks), _party(contractor, chunks)


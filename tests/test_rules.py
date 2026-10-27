from app.extraction.readers import TextChunk
from app.extraction.rules import extract_amount, extract_date, extract_number, extract_parties


def chunks(*lines: str) -> list[TextChunk]:
    return [TextChunk(line, paragraph_number=index) for index, line in enumerate(lines, start=1)]


def test_extracts_basic_contract_fields() -> None:
    text = chunks(
        "ДОГОВОР ОКАЗАНИЯ УСЛУГ",
        "№ 101/26 от 15.01.2026",
        "Заказчик",
        "ООО «Сибирские решения»",
        "Исполнитель",
        "ИП Иванов Иван Иванович",
        "Сумма договора: 75 000,00 руб.",
    )

    assert extract_number(text).value == "101/26"
    assert extract_date(text).value == "2026-01-15"
    customer, contractor = extract_parties(text)
    assert customer.value == "ООО «Сибирские решения»"
    assert contractor.value == "ИП Иванов Иван Иванович"
    amount, currency = extract_amount(text)
    assert amount.value == 75000.0
    assert currency == "RUB"


def test_marks_ambiguous_amount_for_review() -> None:
    text = chunks(
        "Сумма договора составляет 75 000,00 руб.",
        "Общая стоимость договора составляет 80 000,00 руб.",
    )
    amount, _ = extract_amount(text)
    assert amount.status == "needs_review"
    assert amount.reason is not None


def test_understands_entities_before_roles() -> None:
    text = chunks(
        "ООО «ТрансСиб Экспресс», именуемое далее «Заказчик», и "
        "ООО «Клиника Плюс», именуемое далее «Перевозчик», заключили договор."
    )
    customer, contractor = extract_parties(text)
    assert customer.value == "ООО «ТрансСиб Экспресс»"
    assert contractor.value == "ООО «Клиника Плюс»"


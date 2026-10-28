from app.extraction.ner import extract_named_entities
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


def test_natasha_confirms_rule_based_party() -> None:
    text = chunks("Заказчик | ООО «Ромашка»")
    entities = extract_named_entities(text)
    customer, _ = extract_parties(text, entities)
    assert customer.value == "ООО «Ромашка»"
    assert customer.method == "hybrid:regex+natasha_ner"


def test_understands_full_legal_company_name_and_supplier_roles() -> None:
    text = chunks(
        "ООО «Агромаркет», именуемое в дальнейшем «Поставщик», с одной стороны, и",
        "Акционерное общество «Агрофирма Мценская», именуемое в дальнейшем «Покупатель», с другой стороны.",
    )
    customer, contractor = extract_parties(text)
    assert customer.value == "Акционерное общество «Агрофирма Мценская»"
    assert customer.role_label == "Покупатель"
    assert contractor.value == "ООО «Агромаркет»"
    assert contractor.role_label == "Поставщик"


def test_accepts_money_with_one_decimal_digit() -> None:
    text = chunks("Общая стоимость Товара по Спецификации 440 400,0 рублей.")
    amount, currency = extract_amount(text)
    assert amount.value == 440400.0
    assert currency == "RUB"


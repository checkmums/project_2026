from __future__ import annotations

import json
import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import build_dataset as v1


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "contract_dataset_v1"
DATASET_DIR = ROOT / "contract_dataset_v2"
DOCUMENTS_DIR = DATASET_DIR / "documents"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

PARTIES_A = [
    "ООО «ТрансСиб Экспресс»", "АО «Облачные платформы»", "ООО «Белый кедр»",
    "ООО «МедПрофи»", "АО «ЭнергоКонтур»", "ООО «Академия роста»",
    "ООО «Чистый офис»", "АО «Северная верфь»", "ООО «Городской фестиваль»",
    "ООО «Мебельный квартал»", "АО «ФинЭксперт»", "ООО «Зелёный маршрут»",
    "ООО «Склад 54»", "АО «Медиа Сфера»", "ООО «Точная механика»",
    "ИП Орлова Мария Андреевна", "ИП Никитин Павел Романович",
    "ООО «Восток Девелопмент»", "АО «Цифровая лаборатория»", "ООО «АртЛиния»",
]

PARTIES_B = [
    "ООО «КаргоЛайн»", "ООО «Кодовая мастерская»", "ИП Волков Артём Ильич",
    "ООО «Клиника Плюс»", "АО «ЭнергоСбыт Проект»", "ИП Смирнова Елена Олеговна",
    "ООО «КлинСервис»", "ООО «РемТехСнаб»", "ИП Фёдоров Кирилл Максимович",
    "ООО «Интерьер Комплект»", "ООО «Аудит-Партнёр»", "ООО «ЭкоТранс»",
    "ООО «Хранитель»", "ООО «Реклама Онлайн»", "ИП Козлов Денис Сергеевич",
    "ООО «ФотоЦех»", "АО «Секьюрити Групп»", "ООО «Агентство Север»",
    "ООО «СофтЛицензия»", "ИП Белова Дарья Игоревна",
]

TOPICS = [
    ("Договор перевозки груза", "организовать перевозку партии товара по согласованному маршруту", "Заказчик", "Перевозчик"),
    ("Договор разработки программного обеспечения", "разработать и передать модуль учёта заявок", "Заказчик", "Разработчик"),
    ("Договор хранения", "принять имущество на ответственное хранение", "Поклажедатель", "Хранитель"),
    ("Договор на проведение медицинских осмотров", "провести предварительные медицинские осмотры работников", "Заказчик", "Медицинская организация"),
    ("Договор энергоснабжения", "осуществлять снабжение электрической энергией", "Абонент", "Гарантирующий поставщик"),
    ("Договор оказания образовательных услуг", "провести курс повышения квалификации", "Слушатель", "Образовательная организация"),
    ("Договор клинингового обслуживания", "выполнять ежедневную уборку офисных помещений", "Заказчик", "Исполнитель"),
    ("Договор ремонта оборудования", "выполнить диагностику и ремонт производственной линии", "Заказчик", "Подрядчик"),
    ("Договор организации мероприятия", "организовать деловую конференцию", "Клиент", "Организатор"),
    ("Договор поставки мебели", "изготовить и поставить офисную мебель", "Покупатель", "Поставщик"),
    ("Договор аудиторских услуг", "провести аудит бухгалтерской отчётности", "Заказчик", "Аудитор"),
    ("Договор вывоза отходов", "осуществлять вывоз и передачу отходов на обработку", "Заказчик", "Оператор"),
    ("Договор складского хранения", "разместить товары на складе и обеспечить их сохранность", "Поклажедатель", "Товарный склад"),
    ("Договор рекламных услуг", "разработать и разместить рекламные материалы", "Рекламодатель", "Рекламораспространитель"),
    ("Договор технической поддержки", "обеспечить поддержку информационной системы", "Заказчик", "Исполнитель"),
    ("Договор фотосъёмки", "провести предметную фотосъёмку каталога", "Заказчик", "Фотограф"),
    ("Договор охранных услуг", "обеспечить охрану объекта и пропускной режим", "Заказчик", "Охранная организация"),
    ("Агентский договор", "совершать юридические и фактические действия по поиску клиентов", "Принципал", "Агент"),
    ("Лицензионный договор", "предоставить право использования программного продукта", "Лицензиат", "Лицензиар"),
    ("Договор дизайнерских услуг", "разработать фирменный стиль и комплект макетов", "Заказчик", "Дизайнер"),
    ("Договор аренды оборудования", "передать во временное пользование комплект оборудования", "Арендатор", "Арендодатель"),
    ("Договор бухгалтерского сопровождения", "вести бухгалтерский и налоговый учёт", "Заказчик", "Исполнитель"),
    ("Договор доставки", "осуществлять курьерскую доставку отправлений", "Заказчик", "Служба доставки"),
    ("Договор страхования имущества", "обеспечить страховую защиту имущества", "Страхователь", "Страховщик"),
    ("Договор займа", "передать денежные средства на условиях возвратности", "Заёмщик", "Займодавец"),
    ("Договор на монтаж видеонаблюдения", "поставить и смонтировать систему видеонаблюдения", "Заказчик", "Подрядчик"),
    ("Договор аренды транспортного средства", "предоставить автомобиль без экипажа во временное пользование", "Арендатор", "Арендодатель"),
    ("Договор сопровождения сайта", "обновлять материалы и устранять технические ошибки сайта", "Заказчик", "Исполнитель"),
    ("Договор поставки продуктов питания", "поставлять продукты партиями по заявкам", "Покупатель", "Поставщик"),
    ("Договор лабораторных исследований", "провести лабораторные испытания образцов", "Заказчик", "Лаборатория"),
]

AMOUNTS = [
    42_500, 67_800, 89_990, 103_400, 134_750, 156_000, 199_900, 227_350, 264_000, 298_700,
    345_000, 389_500, 444_444, 512_000, 578_900, 640_000, 715_250, 799_990, 875_000, 930_600,
    1_015_000, 1_190_300, 1_325_000, 1_499_900, 1_680_000, 1_890_750, 2_115_000, 2_460_800,
    2_950_000, 3_480_500, 3_970_000, 4_250_300, 4_890_000, 5_400_000, 6_150_750, 7_200_000,
    8_450_000, 9_990_000, 11_500_000, 13_750_000, 15_200_000, 18_900_000, 21_400_000, 25_000_000,
    29_500_000, 34_800_000, 41_000_000, 47_650_000, 55_000_000, 63_300_000, 72_000_000, 81_500_000,
    94_000_000, 108_750_000, 125_000_000, 146_300_000, 172_000_000, 205_500_000, 248_000_000, 310_000_000,
]

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def amount_text(amount: int, variant: int) -> str:
    separated = f"{amount:,}".replace(",", " ")
    return [
        f"{separated},00 рублей", f"{separated} руб. 00 коп.", f"{separated}.00 RUB",
        f"{separated} рублей, включая НДС 20%", f"{separated} (НДС не облагается)",
    ][variant % 5]


def date_text(value: date, variant: int) -> str:
    return [
        value.strftime("%d.%m.%Y"), value.isoformat(), value.strftime("%d/%m/%Y"),
        f"{value.day} {MONTHS[value.month - 1]} {value.year} года",
        f"«{value.day:02d}» {MONTHS[value.month - 1]} {value.year} г.",
    ][variant % 5]


def make_extended_records() -> list[dict]:
    random.seed(812804)
    records = []
    start = date(2026, 8, 3)
    locations = [
        "номер и дата в правом верхнем блоке; стороны в преамбуле; сумма в разделе 4",
        "все поля в карточке договора на первой странице",
        "номер в заголовке; дата в строке города; стороны в реквизитах; сумма в приложении",
        "сумма до предмета; номер и дата в регистрационных данных в конце",
        "номер и стороны в преамбуле; дата в заголовке; сумма в графике платежей",
        "номер и дата в таблице; стороны в разделе 6; сумма в основном тексте",
        "дата в словесной форме; номер после преамбулы; стороны в подписях; сумма в спецификации",
        "поля распределены между шапкой, вводным абзацем и последней страницей",
        "сумма в коммерческих условиях; стороны обозначены отраслевыми ролями",
        "номер в колонтитульном стиле; дата и стороны ближе к концу документа",
    ]
    for offset in range(60):
        index = 20 + offset
        layout = 5 + offset % 10
        contract_date = start + timedelta(days=offset * 3)
        topic, obligation, customer_role, contractor_role = TOPICS[offset % len(TOPICS)]
        number = [
            f"ТР-{contract_date.year}/{offset + 1:03d}", f"{offset + 21}-КП", f"SLA.{offset + 7:02d}-{contract_date.month}",
            f"REG/{contract_date:%m%y}/{offset + 40}", f"ЛЦ-{chr(1040 + offset % 12)}-{offset + 101}",
        ][offset % 5]
        extension = "docx" if index % 2 == 0 else "pdf"
        records.append({
            "document_id": f"DOC-{index + 1:03d}",
            "filename": f"contract_{index + 1:02d}.{extension}",
            "file_format": extension.upper(),
            "contract_type": topic,
            "contract_number": number,
            "contract_date": contract_date.isoformat(),
            "contract_date_in_text": date_text(contract_date, offset),
            "customer": PARTIES_A[offset % len(PARTIES_A)],
            "contractor": PARTIES_B[(offset * 7 + 3) % len(PARTIES_B)],
            "customer_role": customer_role,
            "contractor_role": contractor_role,
            "amount_rub": AMOUNTS[offset],
            "amount_in_text": amount_text(AMOUNTS[offset], offset),
            "template_variant": f"T{layout}",
            "difficulty": ["medium", "hard", "hard", "very_hard"][offset % 4],
            "field_locations": locations[offset % len(locations)],
            "is_synthetic": True,
            "obligation": obligation,
        })
    return records


def set_docx_font(run, size=10.5, bold=False, color=None):
    run.font.name = "Arial"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Arial")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell(cell, text, bold=False, fill=None):
    cell.text = ""
    run = cell.paragraphs[0].add_run(str(text))
    set_docx_font(run, 9.5, bold)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if fill:
        props = cell._tc.get_or_add_tcPr()
        shade = OxmlElement("w:shd")
        shade.set(qn("w:fill"), fill)
        props.append(shade)


def add_docx_table(document, rows, widths=None, header=False, accent="DCE6F1"):
    table = document.add_table(rows=0, cols=len(rows[0]))
    table.style = "Table Grid"
    for r_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for c_idx, value in enumerate(row):
            set_cell(cells[c_idx], value, bold=(header and r_idx == 0) or c_idx == 0, fill=accent if ((header and r_idx == 0) or c_idx == 0) else None)
    return table


def add_docx_heading(document, text):
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    set_docx_font(p.add_run(text), 11.5, True, "263746")


def add_docx_body(document, text, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = document.add_paragraph()
    p.alignment = align
    set_docx_font(p.add_run(text), 10.5)
    return p


def build_docx(record: dict, path: Path) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Inches(0.55), Inches(0.58)
    sec.left_margin, sec.right_margin = Inches(0.7), Inches(0.7)
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "Arial", Pt(10.5)
    style.paragraph_format.space_after = Pt(5)
    variant = int(record["template_variant"][1:])

    if variant in (6, 10):
        header = sec.header.paragraphs[0]
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_docx_font(header.add_run("РЕЕСТР ДОГОВОРОВ • УЧЕБНЫЙ ОБРАЗЕЦ"), 8, True, "4F6B81")

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_docx_font(title.add_run(record["contract_type"].upper()), 14.5, True, "243746")

    if variant == 5:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_docx_font(p.add_run(f"№ {record['contract_number']}\n{record['contract_date_in_text']}"), 10.5, True)
        add_docx_body(doc, f"{record['customer']}, именуемое далее «{record['customer_role']}», и {record['contractor']}, именуемое далее «{record['contractor_role']}», заключили настоящий договор.")
    elif variant == 6:
        add_docx_table(doc, [["КАРТОЧКА ДОГОВОРА", "ЗНАЧЕНИЕ"], ["Регистрационный номер", record["contract_number"]], ["Дата подписания", record["contract_date_in_text"]], [record["customer_role"], record["customer"]], [record["contractor_role"], record["contractor"]], ["Общая цена", record["amount_in_text"]]], header=True, accent="CFE2F3")
    elif variant == 7:
        add_docx_body(doc, f"г. Новосибирск                                              {record['contract_date_in_text']}", WD_ALIGN_PARAGRAPH.LEFT)
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_docx_font(p.add_run(f"КОНТРАКТ № {record['contract_number']}"), 12, True)
    elif variant == 8:
        add_docx_heading(doc, "КОММЕРЧЕСКИЕ УСЛОВИЯ")
        add_docx_table(doc, [["Стоимость", record["amount_in_text"]], ["Порядок оплаты", "30% аванс, 70% после приёмки"]], accent="FCE5CD")
    elif variant == 9:
        add_docx_body(doc, f"Дата оформления: {record['contract_date_in_text']}", WD_ALIGN_PARAGRAPH.RIGHT)
        add_docx_body(doc, f"{record['customer_role']}: {record['customer']}; {record['contractor_role']}: {record['contractor']}. После согласования условий документу присвоен № {record['contract_number']}.")
    elif variant == 10:
        add_docx_table(doc, [["Номер", record["contract_number"], "Дата", record["contract_date_in_text"]]], accent="D9EAD3")
    elif variant == 11:
        add_docx_body(doc, f"{record['contract_date_in_text']} • Новосибирск", WD_ALIGN_PARAGRAPH.RIGHT)
        add_docx_body(doc, f"Стороны подтверждают намерение сотрудничать на условиях настоящего документа. Регистрационный номер будет указан после преамбулы.")
        add_docx_body(doc, f"№ {record['contract_number']}", WD_ALIGN_PARAGRAPH.CENTER)
    elif variant == 12:
        add_docx_body(doc, f"Внутренний индекс документа: {record['contract_number']}", WD_ALIGN_PARAGRAPH.RIGHT)
        add_docx_body(doc, f"Настоящий документ оформлен {record['contract_date_in_text']}.")
        add_docx_body(doc, f"{record['customer']} ({record['customer_role']}) поручает, а {record['contractor']} ({record['contractor_role']}) принимает обязательства.")
    elif variant == 13:
        add_docx_heading(doc, "ЦЕНА И ОСНОВНЫЕ ПАРАМЕТРЫ")
        add_docx_table(doc, [["Цена", record["amount_in_text"]], ["Срок", "30 календарных дней"], ["Документ", f"№ {record['contract_number']} от {record['contract_date_in_text']}"]], accent="FFF2CC")
    else:
        add_docx_body(doc, f"Лист согласования к документу № {record['contract_number']}", WD_ALIGN_PARAGRAPH.RIGHT)

    add_docx_heading(doc, "1. Предмет договора")
    add_docx_body(doc, f"{record['contractor_role']} обязуется {record['obligation']}, а {record['customer_role']} обязуется принять надлежащее исполнение.")
    add_docx_heading(doc, "2. Порядок исполнения")
    add_docx_body(doc, "Сроки отдельных этапов определяются календарным планом. Результат передаётся по акту, замечания оформляются письменно.")

    if variant in (5, 10, 12):
        add_docx_heading(doc, "3. Цена и расчёты")
        add_docx_body(doc, f"Цена услуг по настоящему договору установлена в размере {record['amount_in_text']}. Оплата производится безналичным переводом.")
    elif variant in (9,):
        add_docx_heading(doc, "3. График платежей")
        add_docx_table(doc, [["Этап", "Доля", "Сумма договора"], ["Аванс", "40%", record["amount_in_text"]], ["Окончательный расчёт", "60%", "в пределах общей цены"]], header=True, accent="EAD1DC")
    elif variant in (7, 11):
        doc.add_page_break()
        add_docx_heading(doc, "ПРИЛОЖЕНИЕ № 1. СПЕЦИФИКАЦИЯ")
        add_docx_table(doc, [["Наименование", "Количество", "Итого"], [record["obligation"].capitalize(), "1 комплект", record["amount_in_text"]]], header=True, accent="D9D2E9")

    add_docx_heading(doc, "4. Ответственность и срок действия")
    add_docx_body(doc, "Стороны несут ответственность в соответствии с законодательством Российской Федерации. Договор действует до полного исполнения обязательств.")

    if variant in (7, 8, 10, 11, 14):
        add_docx_heading(doc, "5. Реквизиты и подписи")
        add_docx_table(doc, [[record["customer_role"], record["contractor_role"]], [record["customer"], record["contractor"]], ["____________ / подпись", "____________ / подпись"]], header=True, accent="D9EAD3")
    if variant in (8, 14):
        add_docx_heading(doc, "РЕГИСТРАЦИОННЫЕ ДАННЫЕ")
        add_docx_body(doc, f"Номер договора: {record['contract_number']}. Дата заключения: {record['contract_date_in_text']}. Заказчик: {record['customer']}. Исполнитель: {record['contractor']}.")
    elif variant not in (6, 7, 8, 10, 11, 14):
        add_docx_table(doc, [[record["customer_role"], record["contractor_role"]], [record["customer"], record["contractor"]]], header=True)

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_docx_font(footer.add_run("Синтетический учебный документ • юридической силы не имеет"), 7.5, False, "777777")
    doc.save(path)


def pdf_styles():
    pdfmetrics.registerFont(TTFont("V2Arial", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("V2ArialBold", FONT_BOLD))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("v2title", parent=base["Title"], fontName="V2ArialBold", fontSize=14, leading=17, alignment=TA_CENTER, textColor=colors.HexColor("#243746"), spaceAfter=8),
        "body": ParagraphStyle("v2body", parent=base["BodyText"], fontName="V2Arial", fontSize=9.8, leading=13, alignment=TA_JUSTIFY, spaceAfter=6),
        "right": ParagraphStyle("v2right", parent=base["BodyText"], fontName="V2Arial", fontSize=9.8, leading=13, alignment=TA_RIGHT, spaceAfter=6),
        "center": ParagraphStyle("v2center", parent=base["BodyText"], fontName="V2ArialBold", fontSize=10.5, leading=14, alignment=TA_CENTER, spaceAfter=6),
        "heading": ParagraphStyle("v2heading", parent=base["Heading2"], fontName="V2ArialBold", fontSize=11, leading=14, textColor=colors.HexColor("#263746"), spaceBefore=7, spaceAfter=4),
        "small": ParagraphStyle("v2small", parent=base["BodyText"], fontName="V2Arial", fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.HexColor("#777777")),
    }


def pdf_table(rows, header=False, accent="#DCE6F1", widths=None):
    safe = [[Paragraph(escape(str(v)), ParagraphStyle("cell", fontName="V2ArialBold" if (r == 0 and header) or c == 0 else "V2Arial", fontSize=8.8, leading=11)) for c, v in enumerate(row)] for r, row in enumerate(rows)]
    table = Table(safe, colWidths=widths)
    commands = [("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#AAB4BD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(accent)))
    else:
        commands.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor(accent)))
    table.setStyle(TableStyle(commands))
    return table


def build_pdf(record: dict, path: Path, styles: dict) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=record["contract_type"], author="Учебный проект")
    v = int(record["template_variant"][1:])
    s = [Paragraph(escape(record["contract_type"].upper()), styles["title"])]
    if v == 5:
        s += [Paragraph(f"<b>№ {escape(record['contract_number'])}</b><br/>{escape(record['contract_date_in_text'])}", styles["right"]), Paragraph(escape(f"{record['customer']}, именуемое далее «{record['customer_role']}», и {record['contractor']}, именуемое далее «{record['contractor_role']}», заключили настоящий договор."), styles["body"])]
    elif v == 6:
        s += [pdf_table([["КАРТОЧКА ДОГОВОРА", "ЗНАЧЕНИЕ"], ["Регистрационный номер", record["contract_number"]], ["Дата подписания", record["contract_date_in_text"]], [record["customer_role"], record["customer"]], [record["contractor_role"], record["contractor"]], ["Общая цена", record["amount_in_text"]]], True, "#CFE2F3", [58 * mm, 102 * mm]), Spacer(1, 7)]
    elif v == 7:
        s += [Paragraph(escape(f"г. Новосибирск                                      {record['contract_date_in_text']}"), styles["body"]), Paragraph(escape(f"КОНТРАКТ № {record['contract_number']}"), styles["center"])]
    elif v == 8:
        s += [Paragraph("КОММЕРЧЕСКИЕ УСЛОВИЯ", styles["heading"]), pdf_table([["Стоимость", record["amount_in_text"]], ["Порядок оплаты", "30% аванс, 70% после приёмки"]], False, "#FCE5CD", [52 * mm, 108 * mm])]
    elif v == 9:
        s += [Paragraph(escape(f"Дата оформления: {record['contract_date_in_text']}"), styles["right"]), Paragraph(escape(f"{record['customer_role']}: {record['customer']}; {record['contractor_role']}: {record['contractor']}. После согласования условий документу присвоен № {record['contract_number']}."), styles["body"])]
    elif v == 10:
        s += [pdf_table([["Номер", record["contract_number"], "Дата", record["contract_date_in_text"]]], False, "#D9EAD3", [25 * mm, 48 * mm, 22 * mm, 50 * mm])]
    elif v == 11:
        s += [Paragraph(escape(f"{record['contract_date_in_text']} • Новосибирск"), styles["right"]), Paragraph("Стороны подтверждают намерение сотрудничать на условиях настоящего документа. Регистрационный номер указан после преамбулы.", styles["body"]), Paragraph(escape(f"№ {record['contract_number']}"), styles["center"])]
    elif v == 12:
        s += [Paragraph(escape(f"Внутренний индекс документа: {record['contract_number']}"), styles["right"]), Paragraph(escape(f"Настоящий документ оформлен {record['contract_date_in_text']}."), styles["body"]), Paragraph(escape(f"{record['customer']} ({record['customer_role']}) поручает, а {record['contractor']} ({record['contractor_role']}) принимает обязательства."), styles["body"])]
    elif v == 13:
        s += [Paragraph("ЦЕНА И ОСНОВНЫЕ ПАРАМЕТРЫ", styles["heading"]), pdf_table([["Цена", record["amount_in_text"]], ["Срок", "30 календарных дней"], ["Документ", f"№ {record['contract_number']} от {record['contract_date_in_text']}"]], False, "#FFF2CC", [45 * mm, 115 * mm])]
    else:
        s += [Paragraph(escape(f"Лист согласования к документу № {record['contract_number']}"), styles["right"])]

    s += [Paragraph("1. Предмет договора", styles["heading"]), Paragraph(escape(f"{record['contractor_role']} обязуется {record['obligation']}, а {record['customer_role']} обязуется принять надлежащее исполнение."), styles["body"]), Paragraph("2. Порядок исполнения", styles["heading"]), Paragraph("Сроки отдельных этапов определяются календарным планом. Результат передаётся по акту, замечания оформляются письменно.", styles["body"])]
    if v in (5, 10, 12):
        s += [Paragraph("3. Цена и расчёты", styles["heading"]), Paragraph(escape(f"Цена услуг по настоящему договору установлена в размере {record['amount_in_text']}. Оплата производится безналичным переводом."), styles["body"])]
    elif v == 9:
        s += [Paragraph("3. График платежей", styles["heading"]), pdf_table([["Этап", "Доля", "Сумма договора"], ["Аванс", "40%", record["amount_in_text"]], ["Окончательный расчёт", "60%", "в пределах общей цены"]], True, "#EAD1DC", [60 * mm, 28 * mm, 72 * mm])]
    elif v in (7, 11):
        s += [PageBreak(), Paragraph("ПРИЛОЖЕНИЕ № 1. СПЕЦИФИКАЦИЯ", styles["heading"]), pdf_table([["Наименование", "Количество", "Итого"], [record["obligation"].capitalize(), "1 комплект", record["amount_in_text"]]], True, "#D9D2E9", [88 * mm, 28 * mm, 44 * mm])]
    s += [Paragraph("4. Ответственность и срок действия", styles["heading"]), Paragraph("Стороны несут ответственность в соответствии с законодательством Российской Федерации. Договор действует до полного исполнения обязательств.", styles["body"])]
    if v in (7, 8, 10, 11, 14):
        s += [Paragraph("5. Реквизиты и подписи", styles["heading"]), pdf_table([[record["customer_role"], record["contractor_role"]], [record["customer"], record["contractor"]], ["____________ / подпись", "____________ / подпись"]], True, "#D9EAD3", [80 * mm, 80 * mm])]
    if v in (8, 14):
        s += [Paragraph("РЕГИСТРАЦИОННЫЕ ДАННЫЕ", styles["heading"]), Paragraph(escape(f"Номер договора: {record['contract_number']}. Дата заключения: {record['contract_date_in_text']}. Заказчик: {record['customer']}. Исполнитель: {record['contractor']}."), styles["body"])]
    elif v not in (6, 7, 8, 10, 11, 14):
        s += [pdf_table([[record["customer_role"], record["contractor_role"]], [record["customer"], record["contractor"]]], True, "#DCE6F1", [80 * mm, 80 * mm])]
    s += [Spacer(1, 10), Paragraph("Синтетический учебный документ • юридической силы не имеет", styles["small"])]
    doc.build(s)


def write_readme(records):
    text = f"""# Синтетический датасет договоров — версия 2

Набор для учебной разработки и проверки парсера реквизитов договоров.

## Состав

- {len(records)} документов: 40 DOCX и 40 PDF.
- Первые 20 документов совместимы с версией 1.
- 60 новых документов охватывают 30 тематик и 10 дополнительных вариантов верстки.
- Поля намеренно размещены в разных местах: в шапке, преамбуле, таблице-карточке, разделе об оплате, приложении, реквизитах и блоке подписей.
- Используются разные роли сторон: заказчик/исполнитель, покупатель/поставщик, арендатор/арендодатель, принципал/агент и другие.

## Разметка

Эталон находится в `ground_truth.json`, `labels.csv`, `labels.jsonl` и `labels.xlsx`.
Основные поля: номер, дата, логические стороны `customer` и `contractor`, сумма, тема, шаблон и описание расположения полей.

Все названия, реквизиты и суммы вымышлены. Документы не имеют юридической силы.
"""
    (DATASET_DIR / "README.md").write_text(text, encoding="utf-8")


def main():
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    original = json.loads((SOURCE_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    for record in original:
        shutil.copy2(SOURCE_DIR / "documents" / record["filename"], DOCUMENTS_DIR / record["filename"])
        record.setdefault("field_locations", "базовый шаблон версии 1")
    extended = make_extended_records()
    styles = pdf_styles()
    for record in extended:
        output = DOCUMENTS_DIR / record["filename"]
        if record["file_format"] == "DOCX":
            build_docx(record, output)
        else:
            build_pdf(record, output, styles)
    public = [{k: val for k, val in rec.items() if k not in {"obligation", "customer_role", "contractor_role"}} for rec in extended]
    all_records = original + public
    (DATASET_DIR / "ground_truth.json").write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ["schema.sql", "architecture.md", "architecture.svg", "architecture.png"]:
        source = SOURCE_DIR / name
        if source.exists():
            shutil.copy2(source, DATASET_DIR / name)
    write_readme(all_records)
    print(f"Created dataset v2: {len(all_records)} documents ({len(extended)} new)")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.extraction import extract_contract  # noqa: E402


FIELDS = ("contract_number", "contract_date", "customer", "contractor", "amount")
GROUND_TRUTH_FIELDS = {"amount": "amount_rub"}


def normalize(field: str, value: object) -> str:
    if value is None:
        return ""
    if field == "amount":
        return str(float(value))
    return " ".join(str(value).lower().replace("ё", "е").split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Оценка rule-based парсера на размеченном датасете")
    parser.add_argument("--limit", type=int, default=None, help="Обработать только первые N документов")
    parser.add_argument("--difficulty", help="Фильтр сложности, например easy")
    args = parser.parse_args()

    dataset_dir = PROJECT_ROOT / "contract_dataset_v2"
    records = json.loads((dataset_dir / "ground_truth.json").read_text(encoding="utf-8"))
    if args.difficulty:
        records = [record for record in records if record.get("difficulty") == args.difficulty]
    if args.limit:
        records = records[: args.limit]

    correct = Counter()
    predicted = Counter()
    errors: list[dict[str, str]] = []
    complete = 0
    for record in records:
        path = dataset_dir / "documents" / record["filename"]
        result = extract_contract(path, record["file_format"].upper(), "rules-0.2.0")
        row_complete = True
        for field in FIELDS:
            actual = normalize(field, record[GROUND_TRUTH_FIELDS.get(field, field)])
            output = getattr(result, field)
            value = normalize(field, output.value)
            if value:
                predicted[field] += 1
            if value == actual:
                correct[field] += 1
            else:
                row_complete = False
                errors.append({"filename": record["filename"], "field": field, "expected": actual, "actual": value})
        complete += int(row_complete)

    total = len(records)
    print(f"Документов: {total}; полностью корректных: {complete}/{total} ({complete / total:.1%})" if total else "Нет документов")
    for field in FIELDS:
        recall = correct[field] / total if total else 0
        precision = correct[field] / predicted[field] if predicted[field] else 0
        print(f"{field:16} precision={precision:.1%} coverage={predicted[field] / total:.1%} exact={recall:.1%}")
    if errors:
        print("\nПервые ошибки:")
        for error in errors[:15]:
            print(f"- {error['filename']} {error['field']}: {error['actual']!r} != {error['expected']!r}")


if __name__ == "__main__":
    main()


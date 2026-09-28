import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2] ?? "project_start_materials/contract_dataset_v1");
const records = JSON.parse(await fs.readFile(path.join(root, "ground_truth.json"), "utf8"));
const headers = [
  "document_id", "filename", "file_format", "contract_type", "contract_number",
  "contract_date", "customer", "contractor", "amount_rub", "template_variant",
  "difficulty", "field_locations", "is_synthetic",
];

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

const csv = [headers.join(","), ...records.map(row => headers.map(key => csvValue(row[key])).join(","))].join("\n") + "\n";
await fs.writeFile(path.join(root, "labels.csv"), csv, "utf8");
await fs.writeFile(path.join(root, "labels.jsonl"), records.map(row => JSON.stringify(row)).join("\n") + "\n", "utf8");

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Разметка");
sheet.showGridLines = false;
const rowCount = records.length + 1;
const lastRow = rowCount;
sheet.getRange("A1:M1").values = [[
  "ID", "Файл", "Формат", "Тип договора", "Номер договора", "Дата",
  "Заказчик", "Исполнитель", "Сумма руб", "Шаблон", "Сложность", "Расположение полей", "Синтетический",
]];
sheet.getRange(`A2:M${lastRow}`).values = records.map(row => [
  row.document_id, row.filename, row.file_format, row.contract_type, row.contract_number,
  row.contract_date.split("-").reverse().join("."), row.customer, row.contractor, row.amount_rub,
  row.template_variant, row.difficulty, row.field_locations ?? "базовый шаблон", row.is_synthetic,
]);
sheet.getRange(`A1:M${lastRow}`).format.font = { name: "Arial", size: 10, color: "#222222" };
sheet.getRange("A1:M1").format = {
  fill: "#315B7D",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D9E1E8" },
};
sheet.getRange(`A2:M${lastRow}`).format.verticalAlignment = "center";
sheet.getRange(`A2:M${lastRow}`).format.borders = { preset: "inside", style: "thin", color: "#E1E5E8" };
sheet.getRange(`D2:D${lastRow}`).format.wrapText = true;
sheet.getRange(`G2:H${lastRow}`).format.wrapText = true;
sheet.getRange(`L2:L${lastRow}`).format.wrapText = true;
sheet.getRange(`F2:F${lastRow}`).format.numberFormat = "@";
sheet.getRange(`I2:I${lastRow}`).format.numberFormat = "#,##0";
sheet.getRange(`A2:C${lastRow}`).format.horizontalAlignment = "center";
sheet.getRange(`E2:F${lastRow}`).format.horizontalAlignment = "center";
sheet.getRange(`I2:M${lastRow}`).format.horizontalAlignment = "center";
sheet.getRange(`A1:M${lastRow}`).format.autofitRows();
const widths = [90, 125, 70, 245, 115, 95, 210, 220, 100, 80, 90, 300, 105];
for (let index = 0; index < widths.length; index += 1) {
  sheet.getRangeByIndexes(0, index, rowCount, 1).format.columnWidthPx = widths[index];
}
sheet.freezePanes.freezeRows(1);
sheet.tables.add(`A1:M${lastRow}`, true, "DatasetLabels").style = "TableStyleMedium2";

workbook.recalculate();
const inspection = await workbook.inspect({
  kind: "table",
  range: `Разметка!A1:M${Math.min(lastRow, 12)}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 13,
  maxChars: 12000,
});
console.log(inspection.ndjson);
await fs.mkdir(path.resolve("tmp/dataset_qa"), { recursive: true });
const previewRanges = records.length > 25
  ? [["A1:M28", "labels_preview_1.png"], ["A29:M55", "labels_preview_2.png"], [`A56:M${lastRow}`, "labels_preview_3.png"]]
  : [[`A1:M${lastRow}`, "labels_preview.png"]];
for (const [range, filename] of previewRanges) {
  const preview = await workbook.render({ sheetName: "Разметка", range, scale: 1, format: "png" });
  await fs.writeFile(path.resolve("tmp/dataset_qa", filename), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(root, "labels.xlsx"));

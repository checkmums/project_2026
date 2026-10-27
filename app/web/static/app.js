const fileInput = document.querySelector("#file-input");
const uploadButton = document.querySelector("#upload-button");
const fileName = document.querySelector("#file-name");
const message = document.querySelector("#message");
const registryBody = document.querySelector("#registry-body");
const emptyState = document.querySelector("#empty-state");
const documentCount = document.querySelector("#document-count");
const searchInput = document.querySelector("#search-input");
const dialog = document.querySelector("#details-dialog");
const detailsContent = document.querySelector("#details-content");
const deleteButton = document.querySelector("#delete-button");
let activeDocumentId = null;
let searchTimer = null;

const statusLabels = {
  processed: "Обработан",
  needs_review: "Требует проверки",
  error: "Ошибка",
  found: "Найдено",
  not_found: "Не найдено"
};

const fieldLabels = {
  contract_number: "Номер договора",
  contract_date: "Дата договора",
  customer: "Заказчик",
  contractor: "Исполнитель",
  amount: "Сумма"
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
  message.hidden = false;
}

function statusBadge(status) {
  return `<span class="status ${escapeHtml(status)}">${statusLabels[status] || escapeHtml(status)}</span>`;
}

function formatAmount(value, currency) {
  if (value === null || value === undefined) return "—";
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value)} ${currency || ""}`.trim();
}

async function loadRegistry() {
  const query = searchInput.value.trim();
  const response = await fetch(`/api/v1/contracts${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  if (!response.ok) throw new Error("Не удалось загрузить реестр");
  const documents = await response.json();
  registryBody.innerHTML = documents.map((document) => `
    <tr data-id="${escapeHtml(document.document_uid)}">
      <td class="filename">${escapeHtml(document.filename)}</td>
      <td>${escapeHtml(document.contract_number || "—")}</td>
      <td>${escapeHtml(document.contract_date || "—")}</td>
      <td>${escapeHtml(document.customer || "—")}</td>
      <td>${escapeHtml(document.contractor || "—")}</td>
      <td>${formatAmount(document.amount, document.currency)}</td>
      <td>${statusBadge(document.processing_status)}</td>
    </tr>
  `).join("");
  documentCount.textContent = `${documents.length} ${documents.length === 1 ? "договор" : "договоров"}`;
  emptyState.hidden = documents.length !== 0;
}

fileInput.addEventListener("change", () => {
  const count = fileInput.files.length;
  fileName.textContent = count === 0 ? "Файл не выбран" : count === 1 ? fileInput.files[0].name : `Выбрано файлов: ${count}`;
  uploadButton.disabled = count === 0;
});

uploadButton.addEventListener("click", async () => {
  uploadButton.disabled = true;
  uploadButton.textContent = "Обработка…";
  message.hidden = true;
  try {
    const files = [...fileInput.files];
    const form = new FormData();
    if (files.length === 1) {
      form.append("file", files[0]);
      const response = await fetch("/api/v1/documents", { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Ошибка загрузки");
      showMessage(result.duplicate ? "Этот файл уже был загружен." : "Договор загружен и обработан.");
    } else {
      files.forEach((file) => form.append("files", file));
      const response = await fetch("/api/v1/documents/batch", { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Ошибка загрузки");
      showMessage(`Обработано файлов: ${result.processed.length}. Ошибок: ${result.errors.length}.`, result.errors.length > 0);
    }
    fileInput.value = "";
    fileName.textContent = "Файл не выбран";
    await loadRegistry();
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    uploadButton.textContent = "Загрузить";
    uploadButton.disabled = fileInput.files.length === 0;
  }
});

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadRegistry().catch((error) => showMessage(error.message, true)), 250);
});

registryBody.addEventListener("click", async (event) => {
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  const response = await fetch(`/api/v1/documents/${row.dataset.id}`);
  if (!response.ok) return showMessage("Не удалось открыть документ", true);
  const record = await response.json();
  activeDocumentId = record.document_uid;
  document.querySelector("#details-title").textContent = record.contract_number ? `Договор № ${record.contract_number}` : "Карточка договора";
  document.querySelector("#details-subtitle").textContent = record.filename;
  detailsContent.innerHTML = Object.entries(fieldLabels).map(([key, label]) => {
    const field = record.extraction[key];
    const value = key === "amount" ? formatAmount(field.value, record.extraction.currency) : field.value || "Не найдено";
    return `<div class="field-row">
      <div class="field-heading"><span class="field-name">${label}</span>${statusBadge(field.status)}</div>
      <div class="field-value">${escapeHtml(value)}</div>
      ${field.evidence ? `<div class="evidence">Источник: ${escapeHtml(field.evidence)}</div>` : ""}
    </div>`;
  }).join("");
  dialog.showModal();
});

function closeDialog() { dialog.close(); }
document.querySelector("#close-dialog").addEventListener("click", closeDialog);
document.querySelector("#close-dialog-bottom").addEventListener("click", closeDialog);

deleteButton.addEventListener("click", async () => {
  if (!activeDocumentId || !window.confirm("Удалить этот документ из реестра?")) return;
  const response = await fetch(`/api/v1/documents/${activeDocumentId}`, { method: "DELETE" });
  if (!response.ok) return showMessage("Не удалось удалить документ", true);
  closeDialog();
  showMessage("Документ удалён.");
  await loadRegistry();
});

loadRegistry().catch((error) => showMessage(error.message, true));

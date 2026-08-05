(() => {
  "use strict";

  const API = "/api/package-reconciliation/jobs";
  const POLL_DELAY_MS = 900;
  const STATUS_PROCESSING = "processing";
  const STATUS_READY = "ready";
  const STATUS_FAILED = "failed";
  const MAX_PACKAGE_FILES = 128;
  const WORKBOOK_EXTENSIONS = new Set([".xlsx", ".xlsm", ".ods"]);
  const ALLOWED_EXTENSIONS = new Set([...WORKBOOK_EXTENSIONS, ".pdf"]);
  const STATUS_ORDER = ["MATCH", "MISMATCH", "AMBIGUOUS", "NO_EVIDENCE", "NEEDS_REVIEW"];
  const STATUS_LABELS = {
    MATCH: "подтверждено",
    MISMATCH: "расхождение",
    AMBIGUOUS: "несколько кандидатов",
    NO_EVIDENCE: "нет доказательства",
    NEEDS_REVIEW: "нужна проверка",
  };
  const REASON_LABELS = {
    missing_work_code: "в строке нет кода работы",
    no_exact_work_code_candidate: "не найден кандидат с точным кодом работы",
    unsupported_document_type: "найден документ неподходящего типа",
    multiple_unsupported_candidates: "найдено несколько документов неподходящего типа",
    independent_content_signal_missing: "не найден независимый признак сопоставления",
    equally_strong_candidates: "несколько кандидатов имеют одинаковую силу доказательств",
    low_ocr_confidence: "распознанный текст PDF недостаточно надёжен",
    pdf_text_unavailable: "текст PDF недоступен для безопасной проверки",
    project_code_match: "совпадает код проекта",
    work_description_similarity: "сопоставлено описание работы",
  };
  const form = document.querySelector("#package-form");
  const filesInput = document.querySelector("#package-files");
  const count = document.querySelector("#package-file-count");
  const status = document.querySelector("#status");
  const errors = document.querySelector("#error-list");
  const start = document.querySelector("#start-package-job");
  const report = document.querySelector("#package-report");
  const summary = document.querySelector("#status-summary");
  const evidence = document.querySelector("#evidence-body");
  const empty = document.querySelector("#package-empty");
  const download = document.querySelector("#package-download");
  let jobId = "";
  let pollTimer = 0;

  const text = (value, fallback = "—") => typeof value === "string" && value ? value : fallback;
  const scalar = (value, fallback = "—") => (typeof value === "string" && value) || typeof value === "number" ? String(value) : fallback;
  const list = (value) => Array.isArray(value) ? value : [];
  const object = (value) => value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const isTerminal = (value) => [STATUS_READY, "completed", "complete", STATUS_FAILED, "error"].includes(String(value).toLowerCase());
  const isReady = (value) => [STATUS_READY, "completed", "complete"].includes(String(value).toLowerCase());
  const extension = (file) => {
    const name = text(file?.name, "");
    return name.includes(".") ? `.${name.split(".").at(-1).toLowerCase()}` : "";
  };
  const statusLabel = (value) => STATUS_LABELS[text(value, "NEEDS_REVIEW").toUpperCase()] || "нужна проверка";
  const reasonLabel = (value) => REASON_LABELS[String(value)] || String(value).replaceAll("_", " ");

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const setProgress = (step) => {
    const active = ["files", "run", "result"].indexOf(step);
    document.querySelectorAll("[data-progress]").forEach((item, index) => {
      item.classList.toggle("is-active", index === active);
      item.classList.toggle("is-complete", index < active);
    });
  };

  const showErrors = (items) => {
    errors.replaceChildren();
    list(items).slice(0, 10).forEach((item) => {
      const line = document.createElement("li");
      line.textContent = typeof item === "string" ? item : text(object(item).message || object(item).error, "Сверка не выполнена.");
      errors.append(line);
    });
    errors.hidden = !errors.childElementCount;
  };

  const updateCount = () => {
    const files = [...filesInput.files];
    const roots = new Set(files.map((file) => text(file.webkitRelativePath, file.name).split("/")[0]));
    count.textContent = files.length
      ? `Выбрано файлов: ${files.length}${roots.size === 1 ? ` · папка «${[...roots][0]}»` : ""}`
      : "Папка пока не выбрана";
    showErrors([]);
  };

  const selectionErrors = (files) => {
    const issues = [];
    if (files.length > MAX_PACKAGE_FILES) issues.push(`В папке больше ${MAX_PACKAGE_FILES} файлов. Выберите пакет меньшего размера.`);
    const unsupported = files.filter((file) => !ALLOWED_EXTENSIONS.has(extension(file)));
    if (unsupported.length) issues.push("В папке есть неподдерживаемые файлы. Оставьте только .xlsx, .xlsm, .ods и .pdf.");
    if (!files.some((file) => WORKBOOK_EXTENSIONS.has(extension(file)))) issues.push("Добавьте хотя бы одну таблицу .xlsx, .xlsm или LibreOffice Calc .ods.");
    return issues;
  };

  const requestJson = async (url, options = {}) => {
    let response;
    try {
      response = await fetch(url, options);
    } catch {
      throw new Error("Не удалось связаться с локальной панелью. Проверьте, что она запущена, и повторите действие.");
    }
    let payload = {};
    try { payload = await response.json(); } catch { /* An empty success body is not a report. */ }
    if (!response.ok) {
      const error = new Error(text(payload.error || payload.message, "Сверка не выполнена. Проверьте выбранную папку."));
      error.payload = payload;
      throw error;
    }
    return payload;
  };

  const statusSummary = (payload, rows) => {
    const supplied = object(payload.summary || payload.status_counts || payload.counts);
    const counts = new Map(STATUS_ORDER.map((item) => [item, 0]));
    const hasSuppliedSummary = Object.keys(supplied).length > 0;
    if (hasSuppliedSummary) {
      Object.entries(supplied).forEach(([key, value]) => {
        const status = key.toUpperCase();
        if (counts.has(status) && Number.isFinite(Number(value))) counts.set(status, Number(value));
      });
    } else {
      rows.forEach((row) => {
        const key = text(object(row).status, "NEEDS_REVIEW").toUpperCase();
        if (counts.has(key)) counts.set(key, (counts.get(key) || 0) + 1);
      });
    }
    return STATUS_ORDER.map((item) => [item, counts.get(item) || 0]);
  };

  const appendLine = (cell, value, muted = false) => {
    const line = document.createElement("span");
    line.textContent = text(value);
    if (muted) line.className = "evidence-muted";
    cell.append(line);
  };

  const cell = () => document.createElement("td");
  const renderEvidence = (rows) => {
    evidence.replaceChildren();
    rows.slice(0, 500).forEach((raw) => {
      const row = object(raw);
      const tr = document.createElement("tr");
      const state = text(row.status, "NEEDS_REVIEW");
      const statusCell = cell();
      const badge = document.createElement("span");
      badge.className = `evidence-status is-${state.toLowerCase().replaceAll("_", "-")}`;
      badge.textContent = `${state} · ${statusLabel(state)}`;
      statusCell.append(badge);

      const sourceCell = cell();
      sourceCell.className = "evidence-lines";
      appendLine(sourceCell, row.workbook_path || row.workbook || row.source_path);
      appendLine(sourceCell, row.sheet_name ? `${row.sheet_name} · строка ${scalar(row.row_number)}` : `строка ${scalar(row.row_number)}`, true);

      const codeCell = cell();
      codeCell.textContent = text(row.work_code);
      const pdfCell = cell();
      pdfCell.textContent = text(row.pdf_path || row.evidence_path);
      const comparisonCell = cell();
      comparisonCell.className = "evidence-lines";
      appendLine(comparisonCell, `Excel: ${text(row.workbook_quantity)} ${text(row.workbook_unit, "")}`.trim());
      appendLine(comparisonCell, `АОСР: ${text(row.pdf_quantity)} ${text(row.pdf_unit, "")}`.trim());
      appendLine(comparisonCell, `Проверка: ${text(row.quantity_comparison)}`, true);
      appendLine(comparisonCell, `Стоимость: ${text(row.cost_comparison)}`, true);
      const reasonsCell = cell();
      reasonsCell.textContent = list(row.reason_codes || row.reasons).map(reasonLabel).join("; ") || "—";
      tr.append(statusCell, sourceCell, codeCell, pdfCell, comparisonCell, reasonsCell);
      evidence.append(tr);
    });
    empty.hidden = rows.length !== 0;
  };

  const renderPayload = (payload) => {
    const reportData = object(payload.report || payload.result || payload);
    const rows = list(reportData.results || payload.results || payload.evidence);
    report.hidden = false;
    summary.replaceChildren();
    statusSummary(payload, rows).forEach(([name, value]) => {
      const item = document.createElement("div");
      const term = document.createElement("dt");
      const definition = document.createElement("dd");
      term.textContent = name;
      definition.textContent = String(value);
      item.append(term, definition);
      summary.append(item);
    });
    renderEvidence(rows);
    if (isReady(payload.status)) {
      download.href = `${API}/${encodeURIComponent(jobId)}/result`;
      download.textContent = "Скачать JSON-отчёт";
      download.classList.remove("is-disabled");
      download.removeAttribute("aria-disabled");
      setProgress("result");
    }
  };

  const poll = async () => {
    if (!jobId) return;
    try {
      const payload = await requestJson(`${API}/${encodeURIComponent(jobId)}`);
      renderPayload(payload);
      const current = String(payload.status || "").toLowerCase();
      if (isTerminal(current)) {
        start.disabled = false;
        if (isReady(current)) setStatus("Сверка завершена. Проверьте сводку и скачайте JSON-отчёт.");
        else {
          setStatus(text(payload.error || payload.message, "Сверка не выполнена. Исправьте замечания и запустите снова."), true);
          showErrors(payload.errors || [payload.error || payload.message]);
        }
        return;
      }
      setStatus(current === STATUS_PROCESSING
        ? "Сверяем документы в локальной панели. Можно не закрывать эту страницу."
        : "Задача ожидает обработки в локальной панели.");
      pollTimer = window.setTimeout(poll, POLL_DELAY_MS);
    } catch (error) {
      start.disabled = false;
      setStatus(error.message, true);
      showErrors(error.payload?.errors || [error.message]);
    }
  };

  filesInput.addEventListener("change", updateCount);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    window.clearTimeout(pollTimer);
    const files = [...filesInput.files];
    if (!files.length) {
      setStatus("Выберите папку с хотя бы одной Excel-книгой.", true);
      showErrors(["Папка не выбрана."]);
      filesInput.focus();
      return;
    }
    const invalidSelection = selectionErrors(files);
    if (invalidSelection.length) {
      setStatus("Проверьте состав выбранной папки.", true);
      showErrors(invalidSelection);
      filesInput.focus();
      return;
    }
    const data = new FormData();
    files.forEach((file) => data.append("files", file, file.webkitRelativePath || file.name));
    start.disabled = true;
    download.removeAttribute("href");
    download.textContent = "JSON ещё не готов";
    download.classList.add("is-disabled");
    download.setAttribute("aria-disabled", "true");
    showErrors([]);
    setProgress("run");
    setStatus("Пакет загружается в локальную рабочую область…");
    try {
      const payload = await requestJson(API, { method: "POST", body: data });
      jobId = text(payload.job_id, "");
      if (!jobId) throw new Error("Локальная панель не вернула идентификатор задачи. Повторите запуск.");
      renderPayload(payload);
      if (isTerminal(payload.status)) {
        await poll();
      } else {
        pollTimer = window.setTimeout(poll, POLL_DELAY_MS);
      }
    } catch (error) {
      start.disabled = false;
      setProgress("files");
      setStatus(error.message, true);
      showErrors(error.payload?.errors || [error.message]);
    }
  });
})();

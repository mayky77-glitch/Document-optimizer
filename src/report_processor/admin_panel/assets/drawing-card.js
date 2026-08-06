(() => {
  "use strict";

  const form = document.querySelector("#drawing-card-form");
  const status = document.querySelector("#status");
  const operation = document.querySelector("#operation");
  const existingCardField = document.querySelector("#existing-card-field");
  const existingCard = document.querySelector("#existing-card");
  const sourceFiles = document.querySelector("#sources");
  const sourceCount = document.querySelector("#source-count");
  const period = document.querySelector("#period");
  const createJob = document.querySelector("#create-job");
  const resultDownload = document.querySelector("#result-download");
  const resultHint = document.querySelector("#result-hint");
  const jobIssues = document.querySelector("#job-issues");
  const jobProgress = document.querySelector("#job-progress");
  const jobPhase = document.querySelector("#job-phase");
  const jobProgressBar = document.querySelector("#job-progress-bar");
  const jobFilesProgress = document.querySelector("#job-files-progress");
  const jobRowsProgress = document.querySelector("#job-rows-progress");
  const jobAttempt = document.querySelector("#job-attempt");
  const jobUpdatedAt = document.querySelector("#job-updated-at");
  const cancelJob = document.querySelector("#cancel-job");
  const retryJob = document.querySelector("#retry-job");
  const processingAudit = document.querySelector("#processing-audit");
  const funnelSummary = document.querySelector("#funnel-summary");
  const schemaAuditItems = document.querySelector("#schema-audit-items");
  const exclusionAudit = document.querySelector("#exclusion-audit");
  const exclusionAuditItems = document.querySelector("#exclusion-audit-items");

  const SOURCE_WORKBOOK_EXTENSIONS = new Set([".xlsx", ".xlsm", ".xlsb"]);
  const SESSION_STORAGE_KEY = "report-processor.drawing-card.state.v2";
  const RUSSIAN_MONTHS = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
  ];
  const RUSSIAN_MONTH_NUMBERS = new Map(RUSSIAN_MONTHS.map((name, index) => [name, index + 1]));
  const PERIOD_FROM_FULL_DATE_RE = /(?:^|[^\d])(?:0?[1-9]|[12]\d|3[01])[._/-](?<month>0?[1-9]|1[0-2])[._/-](?<year>\d{4})(?!\d)/u;
  const PERIOD_FROM_YEAR_MONTH_RE = /(?:^|[^\d])(?<year>\d{4})[._-](?<month>0?[1-9]|1[0-2])(?!\d)/u;
  const PERIOD_FROM_MONTH_YEAR_RE = /(?:^|[^\d])(?<month>0?[1-9]|1[0-2])[._-](?<year>\d{4})(?!\d)/u;
  const PERIOD_FROM_RUSSIAN_MONTH_RE = new RegExp(
    `(?:^|[^\\p{L}])(?<month>${RUSSIAN_MONTHS.join("|")})(?=[^\\p{L}]|$)(?:[\\s_-]+[^\\s_-]+){0,2}[\\s_-]+(?<year>\\d{4})(?!\\d)`,
    "u",
  );
  const ZIP_SIGNATURES = [[0x50, 0x4b, 0x03, 0x04], [0x50, 0x4b, 0x05, 0x06], [0x50, 0x4b, 0x07, 0x08]];
  const ACTIVE_JOB_STATUSES = new Set(["queued", "processing"]);
  const TERMINAL_JOB_STATUSES = new Set(["ready", "blocked", "failed", "cancelled"]);
  const JOB_POLL_INTERVAL_MS = 2000;
  const PHASE_LABELS = {
    upload: "Файлы сохранены в приватной задаче",
    schema_detection: "Распознаём структуру таблиц",
    extraction: "Извлекаем строки и значения",
    hierarchy_filtering: "Проверяем структуру и служебные строки",
    matching: "Сопоставляем работы с категориями отчёта",
    review_preparation: "Готовим спорные строки к ручной проверке",
    output_writing: "Формируем итоговый файл",
    validation: "Проверяем итоговый файл перед публикацией",
    ready: "Отчёт проверен и готов к скачиванию",
  };
  let currentJobId = null;
  let currentJobStatus = null;
  let currentReviewPage = 1;
  let periodScanRevision = 0;
  let uploadedSourceCount = 0;
  let currentExclusionAuditUrl = null;
  let idempotencyKey = null;
  let pollTimer = null;

  const sessionState = () => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(SESSION_STORAGE_KEY) || "null");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  };

  const persistSession = (step, reviewPage = currentReviewPage) => {
    try {
      const prior = sessionState();
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
        jobId: currentJobId,
        reviewPage,
        mode: operation.value,
        period: period.value,
        sourceCount: uploadedSourceCount,
        idempotencyKey,
        step: step || prior.step || "sources",
      }));
    } catch {
      // Browser storage is optional.
    }
  };

  const clearSession = () => {
    try {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Browser storage is optional.
    }
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const newIdempotencyKey = () => {
    if (typeof crypto?.randomUUID === "function") return crypto.randomUUID();
    const random = crypto?.getRandomValues?.(new Uint32Array(4));
    return random ? [...random].map((value) => value.toString(16).padStart(8, "0")).join("") : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };

  const progressText = (processed, total, unknown) => Number.isInteger(total)
    ? `${new Intl.NumberFormat("ru-RU").format(processed)} из ${new Intl.NumberFormat("ru-RU").format(total)}`
    : processed > 0
      ? new Intl.NumberFormat("ru-RU").format(processed)
      : unknown;

  const renderJobProgress = (payload) => {
    if (!currentJobId) {
      jobProgress.hidden = true;
      return;
    }
    jobProgress.hidden = false;
    const progress = payload?.progress && typeof payload.progress === "object" ? payload.progress : {};
    const processedFiles = Number.isInteger(progress.processed_files) ? progress.processed_files : 0;
    const totalFiles = Number.isInteger(progress.total_files) ? progress.total_files : null;
    const processedRows = Number.isInteger(progress.processed_rows) ? progress.processed_rows : 0;
    const totalRows = Number.isInteger(progress.total_rows) ? progress.total_rows : null;
    jobPhase.textContent = PHASE_LABELS[payload.phase] || "Уточняем состояние задачи";
    jobFilesProgress.textContent = progressText(processedFiles, totalFiles, "ещё не подсчитаны");
    jobRowsProgress.textContent = progressText(processedRows, totalRows, "ещё не подсчитаны");
    jobAttempt.textContent = new Intl.NumberFormat("ru-RU").format(Math.max(1, Number(payload.attempt) || 1));
    const updated = typeof payload.updated_at === "string" ? new Date(payload.updated_at) : null;
    jobUpdatedAt.textContent = updated && !Number.isNaN(updated.valueOf())
      ? new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(updated)
      : "—";
    const progressValue = totalRows && totalRows > 0
      ? [processedRows, totalRows]
      : totalFiles && totalFiles > 0
        ? [processedFiles, totalFiles]
        : null;
    if (progressValue) {
      jobProgressBar.max = progressValue[1];
      jobProgressBar.value = Math.min(progressValue[0], progressValue[1]);
    } else {
      jobProgressBar.removeAttribute("value");
    }
    cancelJob.hidden = payload.can_cancel !== true;
    retryJob.hidden = payload.can_retry !== true;
  };

  const stopPolling = () => {
    if (pollTimer !== null) window.clearTimeout(pollTimer);
    pollTimer = null;
  };

  const schedulePolling = (statusValue) => {
    stopPolling();
    if (!currentJobId || !ACTIVE_JOB_STATUSES.has(statusValue)) return;
    pollTimer = window.setTimeout(async () => {
      pollTimer = null;
      try {
        const payload = await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}`, { method: "GET" });
        await renderJob(payload, currentReviewPage);
      } catch (error) {
        if (error.status === 404) {
          currentJobId = null;
          currentJobStatus = null;
          clearSession();
          jobProgress.hidden = true;
          setStatus("Задача больше недоступна. Выберите исходные файлы снова.", true);
          return;
        }
        setStatus("Связь с локальной панелью временно прервана. Повторяем проверку статуса…", true);
        schedulePolling(currentJobStatus);
      }
    }, JOB_POLL_INTERVAL_MS);
  };

  const hideIssues = () => {
    jobIssues.replaceChildren();
    jobIssues.hidden = true;
  };

  const renderIssues = (payload, blockingOnly = false) => {
    const source = blockingOnly ? payload?.blocking_reasons : payload?.issues;
    const issues = Array.isArray(source) ? source.slice(0, 8) : [];
    if (!issues.length) {
      hideIssues();
      return;
    }
    jobIssues.replaceChildren(...issues.map((issue) => {
      const item = document.createElement("li");
      item.classList.toggle("is-blocking", issue?.blocking === true);
      const count = Number(issue?.count);
      const suffix = Number.isInteger(count) && count > 1 ? ` (случаев: ${count})` : "";
      const action = typeof issue?.action === "string" && issue.action ? ` ${issue.action}` : "";
      const prefix = issue?.blocking === true ? "Блокирует выпуск: " : "Предупреждение: ";
      item.textContent = `${prefix}${issue?.message || "Обнаружено отклонение."}${suffix}.${action}`.replace("..", ".");
      return item;
    }));
    jobIssues.hidden = false;
  };

  const setProgress = (step) => {
    const current = ["sources", "review", "card"].indexOf(step);
    document.querySelectorAll("[data-progress]").forEach((item, index) => {
      item.classList.toggle("is-active", index === current);
      item.classList.toggle("is-complete", index < current);
    });
    persistSession(step);
  };

  const fileExtension = (file) => {
    const dot = file.name.lastIndexOf(".");
    return dot === -1 ? "" : file.name.slice(dot).toLowerCase();
  };

  const updateSourceCount = () => {
    const count = sourceFiles.files.length;
    if (count) uploadedSourceCount = count;
    sourceCount.textContent = count
      ? `Выбрано исходных файлов: ${count}`
      : uploadedSourceCount
        ? `Уже загружено для текущей карточки: ${uploadedSourceCount}. Чтобы создать новую, выберите файлы снова.`
        : "Файлы пока не выбраны";
    persistSession();
  };

  const canonicalPeriod = (year, month) => {
    const numericYear = Number(year);
    const numericMonth = Number(month);
    if (!Number.isInteger(numericYear) || numericYear < 1 || !Number.isInteger(numericMonth) || numericMonth < 1 || numericMonth > 12) return "";
    return `${String(numericYear).padStart(4, "0")}-${String(numericMonth).padStart(2, "0")}`;
  };

  const extractPeriodFromFilename = (name) => {
    const normalized = typeof name === "string" ? name.toLocaleLowerCase("ru-RU").replaceAll("ё", "е") : "";
    for (const pattern of [PERIOD_FROM_FULL_DATE_RE, PERIOD_FROM_YEAR_MONTH_RE, PERIOD_FROM_MONTH_YEAR_RE]) {
      const match = normalized.match(pattern);
      if (match?.groups) return canonicalPeriod(match.groups.year, match.groups.month);
    }
    const namedMatch = normalized.match(PERIOD_FROM_RUSSIAN_MONTH_RE);
    return namedMatch?.groups ? canonicalPeriod(namedMatch.groups.year, RUSSIAN_MONTH_NUMBERS.get(namedMatch.groups.month)) : "";
  };

  const periodLabel = (value) => `${RUSSIAN_MONTHS[Number(value.slice(5)) - 1]} ${value.slice(0, 4)}`;

  const renderPeriodOptions = (values) => {
    const periods = [...new Set(values)].sort();
    period.replaceChildren(new Option("Последний найденный период", ""));
    periods.forEach((value) => period.append(new Option(periodLabel(value), value)));
    period.value = periods.at(-1) ?? "";
  };

  const selectPeriod = (value) => {
    if (typeof value !== "string" || !value) return;
    if (![...period.options].some((option) => option.value === value)) period.append(new Option(periodLabel(value), value));
    period.value = value;
  };

  const updatePeriodOptions = () => {
    const revision = ++periodScanRevision;
    const filenamePeriods = [...sourceFiles.files].map((file) => extractPeriodFromFilename(file.name)).filter(Boolean);
    renderPeriodOptions(filenamePeriods);
    if (!sourceFiles.files.length) return;
    const data = new FormData();
    [...sourceFiles.files].forEach((file) => data.append("sources", file));
    void fetch("/api/drawing-card/periods", { method: "POST", body: data })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => {
        if (revision !== periodScanRevision || !Array.isArray(payload?.periods)) return;
        const workbookPeriods = payload.periods.map((item) => typeof item?.value === "string" ? item.value : "").filter(Boolean);
        renderPeriodOptions([...filenamePeriods, ...workbookPeriods]);
      })
      .catch(() => {
        // Filename periods remain usable when a workbook cannot be inspected.
      });
  };

  const workbookPreflightError = async (file, allowedExtensions) => {
    const name = typeof file?.name === "string" ? file.name : "выбранный файл";
    const extension = fileExtension(file);
    if (name.startsWith("~$")) return `Файл «${name}» — временный файл Excel. Закройте книгу и выберите файл без префикса «~$».`;
    if (!allowedExtensions.has(extension)) return `Файл «${name}» имеет неподдерживаемый тип. Выберите Excel-файл (${[...allowedExtensions].join(", ")}).`;
    try {
      const bytes = new Uint8Array(await file.slice(0, 4).arrayBuffer());
      if (ZIP_SIGNATURES.some((signature) => signature.every((value, index) => bytes[index] === value))) return "";
    } catch {
      return `Не удалось прочитать файл «${name}». Выберите его снова.`;
    }
    return `Файл «${name}» не является корректной Excel-книгой. Сохраните его в Excel и выберите снова.`;
  };

  const selectedWorkbooksPreflightError = async () => {
    for (const file of sourceFiles.files) {
      const error = await workbookPreflightError(file, SOURCE_WORKBOOK_EXTENSIONS);
      if (error) return error;
    }
    return operation.value === "update" && existingCard.files[0]
      ? workbookPreflightError(existingCard.files[0], new Set([".xlsx"]))
      : "";
  };

  const formError = () => {
    const files = [...sourceFiles.files];
    if (!files.length) return "Добавьте хотя бы один исходный документ.";
    if (files.length > 32) return "Можно выбрать не больше 32 исходных документов. Уберите лишние файлы.";
    if (files.some((file) => !SOURCE_WORKBOOK_EXTENSIONS.has(fileExtension(file)))) return "В исходниках есть неподдерживаемый файл. Оставьте только Excel-файлы .xlsx, .xlsm или .xlsb.";
    if (operation.value === "update" && !existingCard.files.length) return "Для обновления загрузите существующую карточку.";
    if (operation.value === "update" && fileExtension(existingCard.files[0]) !== ".xlsx") return "Существующая карточка должна быть файлом .xlsx.";
    return "";
  };

  const requestJson = async (url, options = {}) => {
    let response;
    try {
      response = await fetch(url, options);
    } catch {
      throw new Error("Не удалось связаться с локальной панелью. Проверьте, что она запущена, и повторите действие.");
    }
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error("Панель вернула непонятный ответ. Повторите действие.");
    }
    if (!response.ok) {
      const error = new Error(typeof payload.error === "string" ? payload.error : "Операция не выполнена. Проверьте данные и повторите действие.");
      error.status = response.status;
      throw error;
    }
    return payload;
  };

  const renderResult = (payload) => {
    if (typeof payload.result_url !== "string" || !payload.result_url) return;
    resultDownload.href = payload.result_url;
    resultDownload.textContent = "Скачать карточку";
    resultDownload.classList.remove("is-disabled");
    resultDownload.removeAttribute("aria-disabled");
    resultHint.textContent = "Карточка готова. Скачайте файл и сохраните его в папке объекта.";
    setProgress("card");
  };

  const resetResult = () => {
    resultDownload.removeAttribute("href");
    resultDownload.textContent = "Скачать карточку";
    resultDownload.classList.add("is-disabled");
    resultDownload.setAttribute("aria-disabled", "true");
    resultHint.textContent = "Здесь появится готовый .xlsx после завершения проверки.";
  };

  const review = new window.DrawingCardReviewPanel({
    requestJson,
    setStatus,
    setProgress,
    renderResult,
    persistSession,
    renderJob: (payload, reviewPage) => renderJob(payload, reviewPage),
  });

  const setOperation = (value, resetIdempotency = false) => {
    const changed = operation.value !== value;
    const isUpdate = value === "update";
    operation.value = value;
    existingCardField.hidden = !isUpdate;
    existingCard.disabled = !isUpdate;
    existingCard.required = isUpdate;
    document.querySelectorAll("[data-operation]").forEach((button) => {
      const selected = button.dataset.operation === value;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    if (resetIdempotency && changed) idempotencyKey = null;
    persistSession();
  };

  const renderJob = async (payload, reviewPage = 1) => {
    currentJobId = typeof payload.job_id === "string" ? payload.job_id : currentJobId;
    currentJobStatus = typeof payload.status === "string" ? payload.status : currentJobStatus;
    createJob.disabled = ACTIVE_JOB_STATUSES.has(currentJobStatus);
    renderJobProgress(payload);
    schedulePolling(currentJobStatus);
    if (payload.mode === "create" || payload.mode === "update") setOperation(payload.mode);
    selectPeriod(payload.period);
    const count = Number(payload?.summary?.source_files);
    if (Number.isInteger(count) && count > 0) {
      uploadedSourceCount = count;
      updateSourceCount();
    }
    renderProcessingAudit(payload);
    resetResult();
    renderResult(payload);
    const needsReview = payload.status === "review_required" || payload.status === "awaiting_review" || payload.can_upload_review || payload.review_url;
    if (needsReview && currentJobId) {
      renderIssues(payload);
      await review.show(payload, currentJobId, reviewPage);
      setStatus("Проверьте группы строк и примените решения.");
      return;
    }
    review.hide();
    if (payload.status === "blocked") {
      renderIssues(payload, true);
      setStatus("Карточка не сформирована: обнаружены блокирующие ошибки. Причины указаны ниже.", true);
    } else if (payload.status === "failed") {
      renderIssues(payload, true);
      setStatus("Обработка завершилась ошибкой. Причина и действие указаны ниже.", true);
    } else if (payload.result_url || payload.status === "ready") {
      renderIssues(payload);
      setStatus("Карточка готова. Скачайте файл.");
    } else if (ACTIVE_JOB_STATUSES.has(payload.status)) {
      hideIssues();
      setStatus(PHASE_LABELS[payload.phase] || "Идёт проверка исходных файлов и формирование отчёта…");
    } else if (payload.status === "cancelled") {
      renderIssues(payload);
      setStatus("Обработка отменена. Частичный файл не опубликован; задачу можно запустить повторно.");
    } else {
      renderIssues(payload);
      setStatus("Статус обработки изменился. Обновите страницу или запустите карточку снова.", true);
    }
    if (TERMINAL_JOB_STATUSES.has(payload.status)) idempotencyKey = null;
    persistSession();
  };

  const appendAuditLine = (root, title, detail, state = "") => {
    const item = document.createElement("p");
    if (state) item.className = `audit-${state}`;
    const strong = document.createElement("strong");
    strong.textContent = title;
    item.append(strong, document.createTextNode(detail ? ` — ${detail}` : ""));
    root.append(item);
  };

  function renderProcessingAudit(payload) {
    const funnel = payload?.funnel;
    const schemas = Array.isArray(payload?.schema_recognition) ? payload.schema_recognition : [];
    if ((!funnel || typeof funnel !== "object") && !schemas.length) {
      processingAudit.hidden = true;
      return;
    }
    processingAudit.hidden = false;
    const labels = [
      ["source_files", "Исходных файлов"],
      ["source_sheets", "Проверено листов"],
      ["extracted_rows", "Извлечено строк"],
      ["skipped_header_rows", "Пропущено заголовков"],
      ["skipped_empty_rows", "Пропущено пустых строк между данными"],
      ["excluded_count", "Исключено структурных строк"],
      ["automatically_accepted_rows", "Принято автоматически"],
      ["manual_review_rows", "Передано на ручную проверку"],
      ["manual_review_groups", "Групп ручной проверки"],
      ["unclassified_count", "Не классифицировано"],
      ["output_rows", "Строк в итоговом отчёте"],
    ];
    funnelSummary.replaceChildren(...labels.flatMap(([key, label]) => {
      const value = Number(funnel?.[key]);
      if (!Number.isFinite(value)) return [];
      const wrapper = document.createElement("div");
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = new Intl.NumberFormat("ru-RU").format(value);
      wrapper.append(term, description);
      return [wrapper];
    }));
    schemaAuditItems.replaceChildren();
    schemas.forEach((schema) => {
      const state = ["recognized", "uncertain", "unsupported"].includes(schema?.recognition)
        ? schema.recognition
        : "unsupported";
      const label = { recognized: "распознано", uncertain: "нужна проверка", unsupported: "не поддерживается" }[state];
      const reasons = Array.isArray(schema?.reason_codes) && schema.reason_codes.length
        ? `; причины: ${schema.reason_codes.join(", ")}`
        : "";
      appendAuditLine(
        schemaAuditItems,
        `${schema?.filename || "Файл"} · ${schema?.sheet_name || "лист"}`,
        `${label}${reasons}`,
        state,
      );
    });
    currentExclusionAuditUrl = typeof payload?.exclusion_audit_url === "string"
      ? payload.exclusion_audit_url
      : null;
    exclusionAudit.hidden = !currentExclusionAuditUrl;
    exclusionAuditItems.replaceChildren();
  }

  exclusionAudit.addEventListener("toggle", async () => {
    if (!exclusionAudit.open || !currentExclusionAuditUrl || exclusionAuditItems.childElementCount) return;
    appendAuditLine(exclusionAuditItems, "Загрузка", "получаем безопасный аудит исключений");
    try {
      const payload = await requestJson(`${currentExclusionAuditUrl}?page=1&page_size=100`);
      exclusionAuditItems.replaceChildren();
      const items = Array.isArray(payload?.items) ? payload.items : [];
      items.forEach((item) => appendAuditLine(
        exclusionAuditItems,
        `${item.filename || "Файл"} · ${item.sheet_name || "лист"} · строка ${item.row_number || "—"}`,
        `${item.reason_code || item.disposition || "Исключено"}; позиция: ${item.position_code || "—"}; роль: ${item.row_role || "—"}`,
      ));
      if (!items.length) appendAuditLine(exclusionAuditItems, "Исключений нет", "все извлечённые строки прошли дальше");
      if (Number(payload?.total) > items.length) {
        appendAuditLine(exclusionAuditItems, "Показаны первые 100 строк", `всего: ${payload.total}`);
      }
    } catch (error) {
      exclusionAuditItems.replaceChildren();
      appendAuditLine(exclusionAuditItems, "Аудит недоступен", error.message);
    }
  });

  document.querySelectorAll("[data-operation]").forEach((button) => button.addEventListener("click", () => setOperation(button.dataset.operation, true)));
  sourceFiles.addEventListener("change", () => {
    idempotencyKey = null;
    updateSourceCount();
    updatePeriodOptions();
  });
  existingCard.addEventListener("change", () => {
    idempotencyKey = null;
    persistSession();
  });
  period.addEventListener("change", () => {
    idempotencyKey = null;
    persistSession();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = formError() || await selectedWorkbooksPreflightError();
    if (error) {
      setStatus(error, true);
      return;
    }
    createJob.disabled = true;
    review.hide();
    hideIssues();
    resetResult();
    setStatus("Проверяем источники и готовим карточку…");
    try {
      idempotencyKey ||= newIdempotencyKey();
      persistSession();
      await renderJob(await requestJson("/api/drawing-card/jobs", {
        method: "POST",
        body: new FormData(form),
        headers: { "Idempotency-Key": idempotencyKey },
      }));
    } catch (requestError) {
      setStatus(requestError.message, true);
    } finally {
      createJob.disabled = ACTIVE_JOB_STATUSES.has(currentJobStatus);
    }
  });

  cancelJob.addEventListener("click", async () => {
    if (!currentJobId) return;
    cancelJob.disabled = true;
    try {
      await renderJob(await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/cancel`, { method: "POST" }));
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      cancelJob.disabled = false;
    }
  });

  retryJob.addEventListener("click", async () => {
    if (!currentJobId) return;
    retryJob.disabled = true;
    try {
      await renderJob(await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/retry`, { method: "POST" }));
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      retryJob.disabled = false;
    }
  });

  const restoreSavedJob = async () => {
    const saved = sessionState();
    if (saved.mode === "create" || saved.mode === "update") setOperation(saved.mode);
    selectPeriod(saved.period);
    uploadedSourceCount = Number.isInteger(saved.sourceCount) && saved.sourceCount > 0 ? saved.sourceCount : 0;
    idempotencyKey = typeof saved.idempotencyKey === "string" && saved.idempotencyKey ? saved.idempotencyKey : null;
    updateSourceCount();
    if (typeof saved.jobId !== "string" || !saved.jobId) {
      if (saved.step === "review" || saved.step === "card") setProgress(saved.step);
      return;
    }
    currentJobId = saved.jobId;
    currentReviewPage = Number.isInteger(saved.reviewPage) && saved.reviewPage > 0 ? saved.reviewPage : 1;
    try {
      await renderJob(await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}`, { method: "GET" }), currentReviewPage);
    } catch (error) {
      if (error.status === 404) {
        currentJobId = null;
        currentJobStatus = null;
        idempotencyKey = null;
        uploadedSourceCount = 0;
        clearSession();
        updateSourceCount();
        setProgress("sources");
        setStatus("Предыдущая карточка больше недоступна. Выберите исходные файлы снова.", true);
        return;
      }
      setStatus("Не удалось восстановить карточку. Повторите действие или выберите файлы снова.", true);
    }
  };

  void restoreSavedJob();
})();

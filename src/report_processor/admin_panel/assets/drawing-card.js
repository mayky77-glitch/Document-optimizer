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
  const reviewPanel = document.querySelector("#review-panel");
  const summary = document.querySelector("#summary");
  const reviewItems = document.querySelector("#review-items");
  const reviewEmpty = document.querySelector("#review-empty");
  const reviewHint = document.querySelector("#review-hint");
  const reviewTemplate = document.querySelector("#review-item-template");
  const approveAll = document.querySelector("#approve-all");
  const rejectAll = document.querySelector("#reject-all");
  const applyReview = document.querySelector("#apply-review");
  const pagination = document.querySelector("#review-pagination");
  const previousPage = document.querySelector("#previous-page");
  const nextPage = document.querySelector("#next-page");
  const pageStatus = document.querySelector("#page-status");
  const legacyReview = document.querySelector("#legacy-review");
  const reviewDownload = document.querySelector("#review-download");
  const reviewForm = document.querySelector("#review-form");
  const submitReview = document.querySelector("#submit-review");
  const resultDownload = document.querySelector("#result-download");
  const resultHint = document.querySelector("#result-hint");

  const SOURCE_WORKBOOK_EXTENSIONS = new Set([".xlsx", ".xlsm", ".xlsb"]);
  const REVIEW_PAGE_SIZE = 50;
  const SESSION_STORAGE_KEY = "report-processor.drawing-card.state.v1";
  const RUSSIAN_MONTHS = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
  ];
  const RUSSIAN_MONTH_NUMBERS = new Map(
    RUSSIAN_MONTHS.map((name, index) => [name, index + 1]),
  );
  const PERIOD_FROM_FULL_DATE_RE =
    /(?:^|[^\d])(?:0?[1-9]|[12]\d|3[01])[._/-](?<month>0?[1-9]|1[0-2])[._/-](?<year>\d{4})(?!\d)/u;
  const PERIOD_FROM_YEAR_MONTH_RE =
    /(?:^|[^\d])(?<year>\d{4})[._-](?<month>0?[1-9]|1[0-2])(?!\d)/u;
  const PERIOD_FROM_MONTH_YEAR_RE =
    /(?:^|[^\d])(?<month>0?[1-9]|1[0-2])[._-](?<year>\d{4})(?!\d)/u;
  const PERIOD_FROM_RUSSIAN_MONTH_RE = new RegExp(
    `(?:^|[^\\p{L}])(?<month>${RUSSIAN_MONTHS.join("|")})(?=[^\\p{L}]|$)(?:[\\s_-]+[^\\s_-]+){0,2}[\\s_-]+(?<year>\\d{4})(?!\\d)`,
    "u",
  );
  const ZIP_SIGNATURES = [
    [0x50, 0x4b, 0x03, 0x04],
    [0x50, 0x4b, 0x05, 0x06],
    [0x50, 0x4b, 0x07, 0x08],
  ];
  let currentJobId = null;
  let currentPage = 1;
  let totalPages = 1;
  let periodScanRevision = 0;
  let uploadedSourceCount = 0;
  let reviewCategories = [];
  let draftCategories = {};

  const sessionState = () => {
    try {
      const value = sessionStorage.getItem(SESSION_STORAGE_KEY);
      const parsed = value ? JSON.parse(value) : null;
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  };

  const persistSession = (step) => {
    try {
      const prior = sessionState();
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
        jobId: currentJobId,
        page: currentPage,
        mode: operation.value,
        period: period.value,
        sourceCount: uploadedSourceCount,
        step: step || prior.step || "sources",
        draftCategories,
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

  const setProgress = (step) => {
    const order = ["sources", "review", "card"];
    const current = order.indexOf(step);
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
    if (
      !Number.isInteger(numericYear) ||
      numericYear < 1 ||
      !Number.isInteger(numericMonth) ||
      numericMonth < 1 ||
      numericMonth > 12
    ) {
      return "";
    }
    return `${String(numericYear).padStart(4, "0")}-${String(numericMonth).padStart(2, "0")}`;
  };

  const extractPeriodFromFilename = (name) => {
    const normalized =
      typeof name === "string"
        ? name.toLocaleLowerCase("ru-RU").replaceAll("ё", "е")
        : "";
    for (const pattern of [
      PERIOD_FROM_FULL_DATE_RE,
      PERIOD_FROM_YEAR_MONTH_RE,
      PERIOD_FROM_MONTH_YEAR_RE,
    ]) {
      const match = normalized.match(pattern);
      if (match?.groups) {
        return canonicalPeriod(match.groups.year, match.groups.month);
      }
    }
    const namedMatch = normalized.match(PERIOD_FROM_RUSSIAN_MONTH_RE);
    return namedMatch?.groups
      ? canonicalPeriod(
          namedMatch.groups.year,
          RUSSIAN_MONTH_NUMBERS.get(namedMatch.groups.month),
        )
      : "";
  };

  const periodLabel = (value) =>
    `${RUSSIAN_MONTHS[Number(value.slice(5)) - 1]} ${value.slice(0, 4)}`;

  const renderPeriodOptions = (values) => {
    const periods = [...new Set(values)].sort();
    period.replaceChildren(new Option("Последний найденный период", ""));
    periods.forEach((value) => period.append(new Option(periodLabel(value), value)));
    period.value = periods.at(-1) ?? "";
  };

  const selectPeriod = (value) => {
    if (typeof value !== "string" || !value) return;
    if (![...period.options].some((option) => option.value === value)) {
      period.append(new Option(periodLabel(value), value));
    }
    period.value = value;
  };

  const discoverPeriodsFromTables = async (revision, filenamePeriods) => {
    const data = new FormData();
    [...sourceFiles.files].forEach((file) => data.append("sources", file));
    if (!sourceFiles.files.length) return;
    try {
      const response = await fetch("/api/drawing-card/periods", {
        method: "POST",
        body: data,
      });
      if (!response.ok) return;
      const payload = await response.json();
      if (revision !== periodScanRevision || !Array.isArray(payload.periods)) return;
      const workbookPeriods = payload.periods
        .map((item) => (typeof item?.value === "string" ? item.value : ""))
        .filter(Boolean);
      renderPeriodOptions([...filenamePeriods, ...workbookPeriods]);
    } catch {
      // Filename periods remain usable when a workbook cannot be inspected.
    }
  };

  const updatePeriodOptions = () => {
    const revision = ++periodScanRevision;
    const filenamePeriods = [...sourceFiles.files]
      .map((file) => extractPeriodFromFilename(file.name))
      .filter(Boolean);
    renderPeriodOptions(filenamePeriods);
    void discoverPeriodsFromTables(revision, filenamePeriods);
  };

  const matchesSignature = (bytes, signature) =>
    signature.every((value, index) => bytes[index] === value);

  const hasZipSignature = (bytes) =>
    ZIP_SIGNATURES.some((signature) => matchesSignature(bytes, signature));

  const workbookPreflightError = async (file, allowedExtensions) => {
    const name =
      typeof file?.name === "string" ? file.name : "выбранный файл";
    const extension = fileExtension(file);
    if (name.startsWith("~$")) {
      return `Файл «${name}» — временный файл Excel. Закройте книгу и выберите файл без префикса «~$».`;
    }
    if (!allowedExtensions.has(extension)) {
      return `Файл «${name}» имеет неподдерживаемый тип. Выберите Excel-файл (${[
        ...allowedExtensions,
      ].join(", ")}).`;
    }
    let bytes;
    try {
      bytes = new Uint8Array(await file.slice(0, 4).arrayBuffer());
    } catch {
      return `Не удалось прочитать файл «${name}». Выберите его снова.`;
    }
    if (!hasZipSignature(bytes)) {
      return `Файл «${name}» не является корректной Excel-книгой. Сохраните его в Excel и выберите снова.`;
    }
    return "";
  };

  const selectedWorkbooksPreflightError = async () => {
    for (const file of sourceFiles.files) {
      const error = await workbookPreflightError(
        file,
        SOURCE_WORKBOOK_EXTENSIONS,
      );
      if (error) return error;
    }
    if (operation.value === "update" && existingCard.files[0]) {
      return workbookPreflightError(existingCard.files[0], new Set([".xlsx"]));
    }
    return "";
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

  const textValue = (value, fallback = "Не указано") => (typeof value === "string" && value.trim() ? value : typeof value === "number" ? String(value) : fallback);

  const valueFrom = (item, keys) => {
    const context = item && typeof item.context === "object" && item.context ? item.context : {};
    for (const key of keys) {
      if (item?.[key] !== undefined && item[key] !== null) return item[key];
      if (context[key] !== undefined && context[key] !== null) return context[key];
    }
    return undefined;
  };

  const humanCategory = (value) => ({
    unit_conflict: "Единицы измерения не совпадают",
    unchanged_value: "Значение не изменилось",
    cost_threshold: "Сумма требует проверки",
    manual_review: "Нужна ручная проверка",
  }[value] || (typeof value === "string" && !value.includes("_") ? value : "Не указана"));

  const decisionLabel = (value) => ({
    approved: "Одобрено",
    rejected: "Отклонено",
    cost_only: "Учтена только стоимость",
    change_category: "Категория изменена",
    pending: "Ожидает решения",
    unresolved: "Ожидает решения",
  }[value] || "Ожидает решения");

  const renderSummary = (values) => {
    summary.replaceChildren();
    if (!values || typeof values !== "object" || Array.isArray(values)) return;
    Object.entries(values).forEach(([label, value]) => {
      if (typeof value !== "string" && typeof value !== "number") return;
      const item = document.createElement("span");
      item.textContent = `${label}: ${value}`;
      summary.append(item);
    });
  };

  const reviewId = (item) => textValue(item.review_id ?? item.id, "");

  const setControlsBusy = (root, busy) => root.querySelectorAll("button, input, select").forEach((control) => { control.disabled = busy; });

  const saveDecision = async (id, action, category) => {
    const payload = { action };
    if (category) payload.category = category;
    return requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review/items/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  };

  const undoDecision = async (id) => requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review/items/${encodeURIComponent(id)}`, { method: "DELETE" });

  const runItemAction = async (button, item, action, category) => {
    const card = button.closest(".review-item");
    const id = reviewId(item);
    if (!id) {
      setStatus("Не удалось определить строку проверки. Обновите страницу и повторите действие.", true);
      return;
    }
    setControlsBusy(card, true);
    try {
      if (action === "undo") await undoDecision(id);
      else await saveDecision(id, action, category);
      delete draftCategories[id];
      setStatus("Решение сохранено.");
      await loadReviewPage(currentPage);
    } catch (error) {
      setStatus(error.message, true);
      setControlsBusy(card, false);
    }
  };

  const renderItem = (item) => {
    const fragment = reviewTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".review-item");
    const id = reviewId(item);
    const state = valueFrom(item, ["decision", "status"]);
    const proposedCategory = valueFrom(item, ["proposed_category_label", "proposed_category"]);
    const selectedCategory = draftCategories[id] || valueFrom(item, ["selected_category", "proposed_category", "category"]);
    card.dataset.reviewId = id;
    card.querySelector(".work-name").textContent = textValue(valueFrom(item, ["work_name", "name", "work"]), "Наименование работы не указано");
    card.querySelector(".decision-status").textContent = decisionLabel(state);
    card.querySelector('[data-context="category"]').textContent = humanCategory(valueFrom(item, ["category_label", "category"]));
    card.querySelector('[data-context="quantity"]').textContent = textValue(valueFrom(item, ["quantity"]));
    card.querySelector('[data-context="source-unit"]').textContent = textValue(valueFrom(item, ["source_unit"]));
    card.querySelector('[data-context="target-unit"]').textContent = textValue(valueFrom(item, ["target_unit"]));
    card.querySelector('[data-context="cost"]').textContent = textValue(valueFrom(item, ["total_cost", "cost"]));
    const proposed = card.querySelector(".proposed-category");
    if (proposedCategory) {
      proposed.hidden = false;
      proposed.textContent = `Предложенная категория: ${humanCategory(proposedCategory)}`;
    }
    const categoryInput = card.querySelector(".category-input");
    categoryInput.replaceChildren(new Option("Выберите категорию", ""));
    reviewCategories.forEach((category) => {
      if (typeof category?.value !== "string" || typeof category?.label !== "string") return;
      categoryInput.append(new Option(category.label, category.value));
    });
    categoryInput.value = typeof selectedCategory === "string" ? selectedCategory : "";
    categoryInput.addEventListener("change", () => {
      if (categoryInput.value) draftCategories[id] = categoryInput.value;
      else delete draftCategories[id];
      persistSession("review");
    });
    const resolved = ["approved", "rejected", "cost_only", "change_category"].includes(state);
    card.querySelector('[data-review-action="undo"]').hidden = !resolved;
    card.querySelectorAll('[data-review-action="approve"], [data-review-action="reject"], [data-review-action="change-category"], [data-review-action="cost-only"]').forEach((button) => { button.hidden = resolved; });
    card.querySelectorAll("[data-review-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.reviewAction;
        if (action === "change-category") {
          const editor = card.querySelector(".category-editor");
          editor.hidden = false;
          categoryInput.focus();
          return;
        }
        if (action === "cancel-category") {
          card.querySelector(".category-editor").hidden = true;
          return;
        }
        const decision = action === "cost-only" ? "cost_only" : action;
        const category = decision === "reject" ? undefined : categoryInput.value;
        if (decision !== "reject" && !category) {
          card.querySelector(".category-editor").hidden = false;
          categoryInput.focus();
          setStatus("Выберите категорию, затем подтвердите решение.", true);
          return;
        }
        runItemAction(button, item, decision, category);
      });
    });
    return fragment;
  };

  const renderReview = (payload) => {
    const items = Array.isArray(payload.items) ? payload.items : [];
    reviewCategories = Array.isArray(payload.categories) ? payload.categories : [];
    reviewItems.replaceChildren(...items.map(renderItem));
    renderSummary(payload.summary);
    reviewEmpty.hidden = items.length !== 0;
    currentPage = Number(payload.page) || currentPage;
    totalPages = Math.max(1, Number(payload.total_pages) || Math.ceil((Number(payload.total) || items.length) / REVIEW_PAGE_SIZE) || 1);
    pagination.hidden = totalPages <= 1;
    previousPage.disabled = currentPage <= 1;
    nextPage.disabled = currentPage >= totalPages;
    const total = Number(payload.total) || items.length;
    const start = total ? ((currentPage - 1) * REVIEW_PAGE_SIZE) + 1 : 0;
    const end = Math.min(currentPage * REVIEW_PAGE_SIZE, total);
    pageStatus.textContent = `Страница ${currentPage} из ${totalPages} · показано ${start}–${end} из ${total}`;
    const unresolved = Number(payload.unresolved ?? payload.unresolved_count);
    applyReview.disabled = Number.isFinite(unresolved) && unresolved > 0;
    reviewHint.textContent = applyReview.disabled ? `Осталось принять решение по строкам: ${unresolved}.` : "Все строки обработаны. Примените решения, чтобы собрать карточку.";
    persistSession("review");
  };

  const loadReviewPage = async (page = 1, moveFocus = false) => {
    if (!currentJobId) return;
    const query = new URLSearchParams({ page: String(page), page_size: String(REVIEW_PAGE_SIZE) });
    const payload = await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review/items?${query}`, { method: "GET" });
    renderReview(payload);
    reviewPanel.hidden = false;
    setProgress("review");
    if (moveFocus) reviewItems.focus({ preventScroll: true });
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

  const showLegacyReview = (payload) => {
    legacyReview.hidden = false;
    reviewDownload.hidden = typeof payload.review_url !== "string" || !payload.review_url;
    if (!reviewDownload.hidden) reviewDownload.href = payload.review_url;
    reviewForm.hidden = payload.can_upload_review !== true;
    approveAll.closest(".bulk-actions").hidden = true;
    reviewItems.hidden = true;
    pagination.hidden = true;
    applyReview.hidden = true;
    reviewHint.textContent = "Проверьте файл замечаний и загрузите исправленную версию.";
  };

  const renderJob = async (payload, reviewPage = 1) => {
    currentJobId = typeof payload.job_id === "string" ? payload.job_id : currentJobId;
    if (payload.mode === "create" || payload.mode === "update") setOperation(payload.mode);
    selectPeriod(payload.period);
    const sourceCountFromJob = Number(payload?.summary?.source_files);
    if (Number.isInteger(sourceCountFromJob) && sourceCountFromJob > 0) {
      uploadedSourceCount = sourceCountFromJob;
      updateSourceCount();
    }
    renderResult(payload);
    const needsReview = payload.status === "review_required" || payload.status === "awaiting_review" || payload.can_upload_review || payload.review_url;
    if (needsReview && currentJobId) {
      legacyReview.hidden = true;
      reviewItems.hidden = false;
      applyReview.hidden = false;
      approveAll.closest(".bulk-actions").hidden = false;
      try {
        await loadReviewPage(reviewPage);
        reviewPanel.focus({ preventScroll: true });
        setStatus("Проверьте строки и примените решения.");
        return;
      } catch (error) {
        if (payload.review_url || payload.can_upload_review) {
          showLegacyReview(payload);
          reviewPanel.hidden = false;
          setProgress("review");
          setStatus("Проверка доступна файлом. Исправьте замечания и загрузите его обратно.");
          return;
        }
        throw error;
      }
    }
    if (payload.result_url) setStatus("Карточка готова. Скачайте файл.");
    else setStatus("Подготовка запущена. Следующий шаг появится в локальной панели.");
    persistSession();
  };

  const setOperation = (value) => {
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
    persistSession();
  };

  const runBulkAction = async (action) => {
    approveAll.disabled = true;
    rejectAll.disabled = true;
    try {
      await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setStatus(action === "approve_all_proposed" ? "Все предложенные категории одобрены." : "Все строки отклонены.");
      await loadReviewPage(currentPage);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      approveAll.disabled = false;
      rejectAll.disabled = false;
    }
  };

  document.querySelectorAll("[data-operation]").forEach((button) => button.addEventListener("click", () => setOperation(button.dataset.operation)));
  sourceFiles.addEventListener("change", () => { updateSourceCount(); updatePeriodOptions(); });
  period.addEventListener?.("change", () => persistSession());
  approveAll.addEventListener("click", () => runBulkAction("approve_all_proposed"));
  rejectAll.addEventListener("click", () => runBulkAction("reject_all"));
  previousPage.addEventListener("click", () => loadReviewPage(currentPage - 1, true));
  nextPage.addEventListener("click", () => loadReviewPage(currentPage + 1, true));

  applyReview.addEventListener("click", async () => {
    applyReview.disabled = true;
    try {
      const payload = await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review/apply`, { method: "POST" });
      renderResult(payload);
      setStatus(payload.result_url ? "Решения применены. Карточка готова." : "Решения применены. Дождитесь подготовки карточки.");
    } catch (error) {
      setStatus(error.message, true);
      applyReview.disabled = false;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = formError() || (await selectedWorkbooksPreflightError());
    if (error) {
      setStatus(error, true);
      return;
    }
    createJob.disabled = true;
    reviewPanel.hidden = true;
    setStatus("Проверяем источники и готовим карточку…");
    try {
      await renderJob(await requestJson("/api/drawing-card/jobs", { method: "POST", body: new FormData(form) }));
    } catch (requestError) {
      setStatus(requestError.message, true);
    } finally {
      createJob.disabled = false;
    }
  });

  reviewForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentJobId || !reviewForm.reportValidity()) {
      setStatus("Сначала подготовьте карточку, затем выберите исправленный файл проверки.", true);
      return;
    }
    submitReview.disabled = true;
    try {
      await renderJob(await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review`, { method: "POST", body: new FormData(reviewForm) }));
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      submitReview.disabled = false;
    }
  });

  const restoreSavedJob = async () => {
    const saved = sessionState();
    if (saved.mode === "create" || saved.mode === "update") setOperation(saved.mode);
    selectPeriod(saved.period);
    uploadedSourceCount = Number.isInteger(saved.sourceCount) && saved.sourceCount > 0
      ? saved.sourceCount
      : 0;
    draftCategories = saved.draftCategories && typeof saved.draftCategories === "object"
      ? saved.draftCategories
      : {};
    updateSourceCount();
    if (typeof saved.jobId !== "string" || !saved.jobId) {
      if (saved.step === "review" || saved.step === "card") setProgress(saved.step);
      return;
    }
    currentJobId = saved.jobId;
    currentPage = Number.isInteger(saved.page) && saved.page > 0 ? saved.page : 1;
    try {
      await renderJob(
        await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}`, { method: "GET" }),
        currentPage,
      );
    } catch (error) {
      if (error.status === 404) {
        currentJobId = null;
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

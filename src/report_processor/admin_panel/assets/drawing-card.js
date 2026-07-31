(() => {
  "use strict";

  const form = document.querySelector("#drawing-card-form");
  const status = document.querySelector("#status");
  const operation = document.querySelector("#operation");
  const existingCardField = document.querySelector("#existing-card-field");
  const existingCard = document.querySelector("#existing-card");
  const createJob = document.querySelector("#create-job");
  const reviewPanel = document.querySelector("#review-panel");
  const reviewDownload = document.querySelector("#review-download");
  const reviewForm = document.querySelector("#review-form");
  const submitReview = document.querySelector("#submit-review");
  const resultDownload = document.querySelector("#result-download");
  const resultHint = document.querySelector("#result-hint");
  const summary = document.querySelector("#summary");
  const warnings = document.querySelector("#warnings");
  const sourceFiles = document.querySelector("#sources");
  const period = document.querySelector("#period");

  const SOURCE_WORKBOOK_EXTENSIONS = new Set([".xlsx", ".xlsm", ".xlsb"]);
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
  const RUSSIAN_MONTH_NUMBERS = new Map(RUSSIAN_MONTHS.map((name, index) => [name, index + 1]));
  const PERIOD_FROM_FULL_DATE_RE = /(?:^|[^\d])(?:0?[1-9]|[12]\d|3[01])[._/-](?<month>0?[1-9]|1[0-2])[._/-](?<year>\d{4})(?!\d)/u;
  const PERIOD_FROM_YEAR_MONTH_RE = /(?:^|[^\d])(?<year>\d{4})[._-](?<month>0?[1-9]|1[0-2])(?!\d)/u;
  const PERIOD_FROM_MONTH_YEAR_RE = /(?:^|[^\d])(?<month>0?[1-9]|1[0-2])[._-](?<year>\d{4})(?!\d)/u;
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

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const fileExtension = (name) => {
    const dot = name.lastIndexOf(".");
    return dot === -1 ? "" : name.slice(dot).toLowerCase();
  };

  const canonicalPeriod = (year, month) => {
    const numericYear = Number(year);
    const numericMonth = Number(month);
    if (!Number.isInteger(numericYear) || numericYear < 1 || !Number.isInteger(numericMonth) || numericMonth < 1 || numericMonth > 12) {
      return "";
    }
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

  const updatePeriodOptions = () => {
    const periods = [...new Set([...sourceFiles.files].map((file) => extractPeriodFromFilename(file.name)).filter(Boolean))].sort();
    period.replaceChildren(new Option("Последний найденный период", ""));
    periods.forEach((value) => {
      const option = new Option(`${RUSSIAN_MONTHS[Number(value.slice(5)) - 1]} ${value.slice(0, 4)}`, value);
      period.append(option);
    });
    period.value = "";
  };

  const matchesSignature = (bytes, signature) => signature.every((value, index) => bytes[index] === value);

  const hasZipSignature = (bytes) => ZIP_SIGNATURES.some((signature) => matchesSignature(bytes, signature));

  const workbookPreflightError = async (file, allowedExtensions) => {
    const name = typeof file?.name === "string" ? file.name : "выбранный файл";
    const extension = fileExtension(name);
    if (name.startsWith("~$")) {
      return `Файл «${name}» — временный файл Excel. Закройте книгу и выберите файл без префикса «~$».`;
    }
    if (!allowedExtensions.has(extension)) {
      return `Файл «${name}» имеет неподдерживаемый тип. Выберите Excel-файл (${[...allowedExtensions].join(", ")}).`;
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
      const error = await workbookPreflightError(file, SOURCE_WORKBOOK_EXTENSIONS);
      if (error) return error;
    }
    if (operation.value === "update" && existingCard.files[0]) {
      return workbookPreflightError(existingCard.files[0], new Set([".xlsx"]));
    }
    return "";
  };

  const setProgress = (step) => {
    const order = ["sources", "review", "card"];
    const current = order.indexOf(step);
    document.querySelectorAll("[data-progress]").forEach((item, index) => {
      item.classList.toggle("is-active", index === current);
      item.classList.toggle("is-complete", index < current);
    });
  };

  const requestJson = async (url, options = {}) => {
    let response;
    try {
      response = await fetch(url, options);
    } catch {
      throw new Error("Не удалось связаться с локальным сервисом. Проверьте, что панель запущена, и повторите действие.");
    }

    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error("Сервис вернул непонятный ответ. Повторите действие; если ошибка останется, запустите подготовку заново.");
    }
    if (!response.ok) {
      throw new Error(typeof payload.error === "string" ? payload.error : "Операция не выполнена. Проверьте выбранные файлы и повторите действие.");
    }
    return payload;
  };

  const textValue = (value) => {
    if (typeof value === "string" || typeof value === "number") return String(value);
    return "";
  };

  const renderSummary = (data) => {
    summary.replaceChildren();
    if (!data || typeof data !== "object" || Array.isArray(data)) return;
    Object.entries(data).forEach(([key, value]) => {
      const valueText = textValue(value);
      if (!valueText) return;
      const item = document.createElement("span");
      item.textContent = `${key}: ${valueText}`;
      summary.append(item);
    });
  };

  const renderWarnings = (items) => {
    warnings.replaceChildren();
    if (!Array.isArray(items)) return;
    items.forEach((item) => {
      const row = document.createElement("li");
      if (typeof item === "string") {
        row.textContent = item;
      } else if (item && typeof item === "object") {
        const message = textValue(item.message) || textValue(item.detail) || textValue(item.code);
        row.textContent = message || "Есть замечание, требующее проверки.";
      }
      if (row.textContent) warnings.append(row);
    });
  };

  const renderResult = (payload) => {
    if (typeof payload.result_url === "string" && payload.result_url) {
      resultDownload.href = payload.result_url;
      resultDownload.textContent = "Скачать карточку";
      resultDownload.classList.remove("is-disabled");
      resultDownload.removeAttribute("aria-disabled");
      resultHint.textContent = "Карточка готова. Скачайте файл и сохраните его в папке объекта.";
      setProgress("card");
      return;
    }
    resultDownload.removeAttribute("href");
    resultDownload.textContent = "Карточка ещё не готова";
    resultDownload.classList.add("is-disabled");
    resultDownload.setAttribute("aria-disabled", "true");
    resultHint.textContent = "Станет доступна после подготовки или загрузки проверки.";
  };

  const reviewIsRequired = (payload) => Boolean(payload.review_url || payload.can_upload_review);

  const renderReview = (payload) => {
    const needsReview = reviewIsRequired(payload);
    reviewPanel.hidden = !needsReview;
    reviewDownload.hidden = true;
    reviewForm.hidden = true;

    if (!needsReview) return;
    renderSummary(payload.summary);
    renderWarnings(payload.warnings);
    if (typeof payload.review_url === "string" && payload.review_url) {
      reviewDownload.href = payload.review_url;
      reviewDownload.hidden = false;
    }
    if (payload.can_upload_review === true) {
      reviewForm.hidden = false;
    }
  };

  const statusMessage = (payload) => {
    const labels = {
      ready: "Карточка готова. Следующий шаг: скачайте файл.",
      completed: "Карточка готова. Следующий шаг: скачайте файл.",
      review_required: "Нужна проверка. Скачайте файл замечаний, исправьте его и загрузите обратно.",
      awaiting_review: "Нужна проверка. Скачайте файл замечаний, исправьте его и загрузите обратно.",
      failed: "Подготовка не завершилась. Проверьте исходные документы и создайте задачу заново.",
    };
    return labels[payload.status] || "Задача обновлена. Проверьте следующий шаг на экране.";
  };

  const renderJob = (payload) => {
    currentJobId = typeof payload.job_id === "string" ? payload.job_id : currentJobId;
    renderReview(payload);
    renderResult(payload);
    if (!payload.result_url && reviewIsRequired(payload)) setProgress("review");
    setStatus(statusMessage(payload), payload.status === "failed");
  };

  const setOperation = (value) => {
    operation.value = value;
    const isUpdate = value === "update";
    existingCardField.hidden = !isUpdate;
    existingCard.disabled = !isUpdate;
    existingCard.required = isUpdate;
    document.querySelectorAll("[data-operation]").forEach((button) => {
      const selected = button.dataset.operation === value;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  };

  document.querySelectorAll("[data-operation]").forEach((button) => {
    button.addEventListener("click", () => setOperation(button.dataset.operation));
  });

  sourceFiles.addEventListener("change", updatePeriodOptions);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) {
      setStatus("Выберите исходные документы. Для обновления также загрузите существующую карточку.", true);
      return;
    }
    createJob.disabled = true;
    try {
      const preflightError = await selectedWorkbooksPreflightError();
      if (preflightError) {
        setStatus(preflightError, true);
        return;
      }
      reviewPanel.hidden = true;
      setProgress("sources");
      setStatus("Проверяем источники и готовим карточку…");
      const payload = await requestJson("/api/drawing-card/jobs", { method: "POST", body: new FormData(form) });
      renderJob(payload);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      createJob.disabled = false;
    }
  });

  reviewForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentJobId) {
      setStatus("Сначала подготовьте карточку, затем загрузите файл проверки.", true);
      return;
    }
    if (!reviewForm.reportValidity()) {
      setStatus("Выберите исправленный файл проверки.", true);
      return;
    }
    submitReview.disabled = true;
    setStatus("Загружаем проверку и обновляем карточку…");
    try {
      const payload = await requestJson(`/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}/review`, { method: "POST", body: new FormData(reviewForm) });
      renderJob(payload);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      submitReview.disabled = false;
    }
  });
})();

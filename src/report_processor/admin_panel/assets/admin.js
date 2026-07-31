(() => {
  "use strict";

  const form = document.querySelector("#job-form");
  const sourceFiles = document.querySelector("#sources");
  const targetFile = document.querySelector("#target");
  const sourceCount = document.querySelector("#source-count");
  const status = document.querySelector("#status");
  const reviewPanel = document.querySelector("#review-panel");
  const summary = document.querySelector("#summary");
  const discrepancies = document.querySelector("#discrepancies");
  const emptyReview = document.querySelector("#empty-review");
  const download = document.querySelector("#download");
  const resultHint = document.querySelector("#result-hint");
  const submit = form.querySelector('button[type="submit"]');
  const workbookExtensions = new Set([".xlsx", ".xlsm", ".xlsb"]);

  const setProgress = (step) => {
    const order = ["files", "run", "result"];
    const current = order.indexOf(step);
    document.querySelectorAll("[data-progress]").forEach((item, index) => {
      item.classList.toggle("is-active", index === current);
      item.classList.toggle("is-complete", index < current);
    });
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };

  const fileExtension = (file) => {
    const dot = file.name.lastIndexOf(".");
    return dot === -1 ? "" : file.name.slice(dot).toLowerCase();
  };

  const updateSourceCount = () => {
    const count = sourceFiles.files.length;
    sourceCount.textContent = count ? `Выбрано исходных файлов: ${count}` : "Файлы пока не выбраны";
  };

  const validationError = () => {
    const sources = [...sourceFiles.files];
    if (!sources.length) return "Добавьте хотя бы один исходный документ.";
    if (sources.length > 32) return "Можно выбрать не больше 32 исходных документов. Уберите лишние файлы.";
    if (sources.some((file) => !workbookExtensions.has(fileExtension(file)))) return "В исходниках есть неподдерживаемый файл. Оставьте только Excel-файлы .xlsx, .xlsm или .xlsb.";
    if (!targetFile.files.length) return "Выберите один целевой отчёт.";
    if (!workbookExtensions.has(fileExtension(targetFile.files[0]))) return "Целевой отчёт должен быть Excel-файлом .xlsx, .xlsm или .xlsb.";
    return "";
  };

  const requestJson = async (url, options) => {
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
      throw new Error("Панель вернула непонятный ответ. Повторите сверку.");
    }
    if (!response.ok) throw new Error(typeof payload.error === "string" ? payload.error : "Сверка не выполнена. Проверьте документы и повторите действие.");
    return payload;
  };

  const humanCategory = (category) => ({
    unit_conflict: "Единицы измерения не совпадают",
    unchanged_value: "Значение не изменилось",
    cost_threshold: "Сумма требует проверки",
    manual_review: "Нужна ручная проверка",
  }[category] || "Требуется проверка");

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

  const renderDiscrepancies = (items) => {
    discrepancies.replaceChildren();
    (Array.isArray(items) ? items : []).forEach((item) => {
      const row = document.createElement("li");
      row.className = item.category || "manual_review";
      const title = document.createElement("strong");
      title.textContent = humanCategory(item.category);
      const detail = document.createElement("span");
      detail.textContent = typeof item.message === "string" && item.message ? item.message : "Проверьте строку в исходном документе и целевом отчёте.";
      row.append(title, detail);
      discrepancies.append(row);
    });
    emptyReview.hidden = discrepancies.children.length !== 0;
  };

  const renderDownload = (payload) => {
    if (typeof payload.download_url === "string" && payload.download_url) {
      download.href = payload.download_url;
      download.textContent = "Скачать результат";
      download.classList.remove("is-disabled");
      download.removeAttribute("aria-disabled");
      resultHint.textContent = "Сверка завершена. Скачайте файл и сохраните его в папке объекта.";
      setProgress("result");
      return;
    }
    download.removeAttribute("href");
    download.textContent = "Результат ещё не готов";
    download.classList.add("is-disabled");
    download.setAttribute("aria-disabled", "true");
  };

  const renderJob = (payload) => {
    renderSummary(payload.summary);
    renderDiscrepancies(payload.discrepancies);
    renderDownload(payload);
    reviewPanel.hidden = false;
    reviewPanel.focus({ preventScroll: true });
    const messages = {
      ready: "Сверка завершена. Результат готов к скачиванию.",
      review_required: "Сверка завершена. Проверьте замечания перед скачиванием результата.",
      failed: "Сверка не завершилась. Проверьте документы и повторите действие.",
    };
    setStatus(messages[payload.status] || (payload.download_url ? "Сверка завершена. Результат готов к скачиванию." : "Сверка выполнена. Проверьте замечания на экране."), payload.status === "failed");
  };

  sourceFiles.addEventListener("change", updateSourceCount);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = validationError();
    if (error) {
      setStatus(error, true);
      return;
    }
    submit.disabled = true;
    reviewPanel.hidden = true;
    setProgress("run");
    setStatus("Сверяем документы…");
    try {
      const data = new FormData();
      [...sourceFiles.files].forEach((file) => data.append("sources", file));
      data.append("target", targetFile.files[0]);
      renderJob(await requestJson("/api/jobs", { method: "POST", body: data }));
    } catch (requestError) {
      setStatus(requestError.message, true);
      setProgress("files");
    } finally {
      submit.disabled = false;
    }
  });
})();

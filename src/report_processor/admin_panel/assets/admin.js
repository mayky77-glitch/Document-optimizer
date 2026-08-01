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
  const suggestionReview = document.querySelector("#suggestion-review");
  const suggestions = document.querySelector("#suggestions");
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

  const suggestionText = (value, fallback) =>
    typeof value === "string" && value.trim() ? value : fallback;

  const scoreText = (value) => {
    const score = Number(value);
    return Number.isFinite(score) ? `${Math.round(score * 100)}%` : "Не указана";
  };

  const unresolvedSuggestions = (payload) => {
    const decided = new Set(
      (Array.isArray(payload.decisions) ? payload.decisions : [])
        .map((item) => item && item.suggestion_id)
        .filter((item) => typeof item === "string"),
    );
    return (Array.isArray(payload.suggestions) ? payload.suggestions : []).filter((item) =>
      item
      && item.requires_manual_review === true
      && typeof item.suggestion_id === "string"
      && !decided.has(item.suggestion_id),
    );
  };

  const manualGroups = (payload) => Array.isArray(payload.manual_review_groups)
    ? payload.manual_review_groups.filter((item) => item
      && typeof item.group_id === "string"
      && Array.isArray(item.discrepancy_ids)
      && item.discrepancy_ids.length > 0)
    : [];

  const renderSuggestion = (item, jobId) => {
    const card = document.createElement("article");
    card.className = "suggestion-card";
    const header = document.createElement("header");
    header.className = "suggestion-card-head";
    const kicker = document.createElement("p");
    kicker.className = "suggestion-kicker";
    kicker.textContent = "Подсказка сопоставления";
    const title = document.createElement("h4");
    title.textContent = suggestionText(item.target_label, "Целевой этап");
    header.append(kicker, title);

    const actions = document.createElement("div");
    actions.className = "suggestion-actions";
    actions.setAttribute("role", "group");
    actions.setAttribute("aria-label", `Решение для «${title.textContent}»`);
    [["Подходит", "fit", "suggestion-fit"], ["Не подходит", "not_fit", "suggestion-not-fit"]].forEach(([label, decision, className]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.addEventListener("click", () => {
        void submitSuggestionDecision(card, jobId, item.suggestion_id, decision);
      });
      actions.append(button);
    });

    const context = document.createElement("dl");
    context.className = "suggestion-context";
    [["Кандидат", suggestionText(item.candidate_label, "Предложенный этап")], ["Цель", suggestionText(item.target_label, "Целевой этап")], ["Оценка", scoreText(item.score)]].forEach(([label, value]) => {
      const entry = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = value;
      entry.append(term, detail);
      context.append(entry);
    });
    card.append(header, actions, context);
    return card;
  };

  const renderManualGroup = (item, jobId) => {
    const card = document.createElement("article");
    card.className = "manual-review-card";
    const header = document.createElement("header");
    header.className = "manual-review-card-head";
    const kicker = document.createElement("p");
    kicker.className = "suggestion-kicker";
    kicker.textContent = "Ручное замечание";
    const title = document.createElement("h4");
    title.textContent = suggestionText(item.title, "Нужна ручная проверка");
    const message = document.createElement("p");
    message.className = "manual-review-message";
    message.textContent = suggestionText(item.message, "Проверьте замечание и примите решение.");
    const count = document.createElement("p");
    count.className = "manual-review-count";
    count.textContent = `Замечаний: ${item.count || item.discrepancy_ids.length}`;
    header.append(kicker, title, message, count);

    const actions = document.createElement("div");
    actions.className = "manual-review-actions";
    actions.setAttribute("role", "group");
    actions.setAttribute("aria-label", `Решение для «${title.textContent}»`);
    [["Одобрить", "approve", "manual-review-approve"], ["Отклонить", "reject", "manual-review-reject"]].forEach(([label, decision, className]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.addEventListener("click", () => {
        void submitManualDecision(card, jobId, item, decision);
      });
      actions.append(button);
    });
    card.append(header, actions);
    return card;
  };

  const renderDiscrepancies = (items, payload) => {
    discrepancies.replaceChildren();
    (Array.isArray(items) ? items : []).forEach((item) => {
      const row = document.createElement("li");
      row.className = item.category || "manual_review";
      const title = document.createElement("strong");
      title.textContent = humanCategory(item.category);
      const detail = document.createElement("span");
      detail.textContent = typeof item.message === "string" && item.message ? item.message : "Проверьте строку в исходном документе и целевом отчёте.";
      row.append(title, detail);
      if (Number.isInteger(item.count) && item.count > 1) {
        const count = document.createElement("span");
        count.className = "discrepancy-count";
        count.textContent = `Повторяется: ${item.count}`;
        row.append(count);
      }
      discrepancies.append(row);
    });
    const pendingSuggestions = unresolvedSuggestions(payload);
    const pendingManualGroups = manualGroups(payload);
    suggestions.replaceChildren(
      ...pendingManualGroups.map((item) => renderManualGroup(item, payload.job_id)),
      ...pendingSuggestions.map((item) => renderSuggestion(item, payload.job_id)),
    );
    suggestionReview.hidden = pendingSuggestions.length + pendingManualGroups.length === 0;
    emptyReview.hidden = discrepancies.children.length !== 0
      || pendingSuggestions.length !== 0 || pendingManualGroups.length !== 0;
  };

  const setSuggestionBusy = (card, busy) => {
    card.querySelectorAll("button").forEach((button) => {
      button.disabled = busy;
    });
  };

  const submitSuggestionDecision = async (card, jobId, suggestionId, decision) => {
    if (typeof jobId !== "string" || !jobId || typeof suggestionId !== "string") {
      setStatus("Не удалось определить подсказку. Обновите страницу и повторите действие.", true);
      return;
    }
    setSuggestionBusy(card, true);
    try {
      const payload = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suggestion_id: suggestionId, decision }),
      });
      renderJob(payload);
    } catch (error) {
      setSuggestionBusy(card, false);
      setStatus(error.message, true);
    }
  };

  const submitManualDecision = async (card, jobId, group, decision) => {
    if (typeof jobId !== "string" || !jobId || typeof group.group_id !== "string") {
      setStatus("Не удалось определить группу замечаний. Обновите страницу и повторите действие.", true);
      return;
    }
    setSuggestionBusy(card, true);
    try {
      const payload = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/manual-discrepancy-decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          group_id: group.group_id,
          discrepancy_ids: group.discrepancy_ids,
          decision,
        }),
      });
      renderJob(payload);
    } catch (error) {
      setSuggestionBusy(card, false);
      setStatus(error.message, true);
    }
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
    renderDiscrepancies(payload.discrepancies, payload);
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

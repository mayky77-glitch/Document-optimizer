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

  const decimalText = (value) => Number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const unresolvedSuggestions = (payload) => Array.isArray(payload.suggestion_review_groups)
    ? payload.suggestion_review_groups.filter((item) => item
      && typeof item.group_id === "string"
      && Array.isArray(item.candidates)
      && item.candidates.length > 0)
    : [];

  const manualGroups = (payload) => Array.isArray(payload.manual_review_groups)
    ? payload.manual_review_groups.filter((item) => item
      && typeof item.group_id === "string"
      && Number.isInteger(item.count)
      && item.count > 0)
    : [];

  const contextCells = (context, extras = []) => {
    const labels = {
      source_unit: "Ед. в источнике",
      target_unit: "Ед. в цели",
      proposed_match: "Предложенное соответствие",
      reason: "Причина",
      aggregate_cost: "Расчётная стоимость",
      confidence: "Уверенность",
      member_count: "Замечаний в группе",
    };
    const cells = [...extras, ...Object.entries(context && typeof context === "object" ? context : {})]
      .filter(([key, value]) => labels[key] && value !== "" && value !== null && value !== undefined)
      .slice(0, 6);
    const list = document.createElement("dl");
    list.className = "review-context";
    cells.forEach(([key, value]) => {
      const entry = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = labels[key];
      const detail = document.createElement("dd");
      detail.textContent = key === "confidence"
        ? scoreText(value)
        : ["aggregate_cost", "quantity", "cost"].includes(key) && Number.isFinite(Number(value))
          ? `${decimalText(value)}${key.includes("cost") ? " ₽" : ""}`
          : String(value);
      entry.append(term, detail);
      list.append(entry);
    });
    return list;
  };

  const composition = (members, hasMore, kind = "member") => {
    const details = document.createElement("details");
    details.className = "review-composition";
    const summary = document.createElement("summary");
    summary.textContent = hasMore ? "Состав группы (показана часть)" : "Состав группы";
    const table = document.createElement("table");
    table.innerHTML = kind === "candidate"
      ? "<thead><tr><th>Кандидат</th><th>Ед.</th><th>Уверенность</th></tr></thead>"
      : "<thead><tr><th>Работа</th><th>Ед.</th><th>Количество</th><th>Стоимость</th></tr></thead>";
    const body = document.createElement("tbody");
    (Array.isArray(members) ? members : []).forEach((member) => {
      const row = document.createElement("tr");
      const context = member && member.context || {};
      const values = kind === "candidate"
        ? [member && member.title, context.source_unit, context.confidence]
        : [member && member.title, context.source_unit, context.quantity, context.cost];
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = kind === "candidate" && value === context.confidence
          ? scoreText(value)
          : [context.quantity, context.cost].includes(value) && Number.isFinite(Number(value))
            ? `${decimalText(value)}${value === context.cost ? " ₽" : ""}`
            : suggestionText(value, "—");
        row.append(cell);
      });
      body.append(row);
    });
    table.append(body);
    details.append(summary, table);
    return details;
  };

  const renderSuggestion = (item, jobId) => {
    const card = document.createElement("article");
    card.className = "review-item suggestion-card";
    const header = document.createElement("header");
    header.className = "review-item-head";
    const kicker = document.createElement("p");
    kicker.className = "review-kicker";
    kicker.textContent = `Подсказки сопоставления · ${item.count || item.candidates.length}`;
    const title = document.createElement("h3");
    title.textContent = suggestionText(item.title, "Целевой этап");
    const status = document.createElement("p");
    status.className = "decision-status";
    status.textContent = "Требует решения";
    header.append(document.createElement("div"), status);
    header.firstElementChild.append(kicker, title);

    const select = document.createElement("select");
    select.className = "suggestion-candidate";
    select.setAttribute("aria-label", "Выберите подходящее соответствие");
    item.candidates.forEach((candidate) => {
      const option = document.createElement("option");
      option.value = candidate.suggestion_id;
      option.textContent = `${suggestionText(candidate.label, "Предложенный этап")} · ${scoreText(candidate.confidence)}`;
      select.append(option);
    });
    const actions = document.createElement("div");
    actions.className = "review-decision-actions";
    actions.setAttribute("role", "group");
    actions.setAttribute("aria-label", `Решение для «${title.textContent}»`);
    [["Применить", "apply", "suggestion-fit"], ["Отклонить", "reject", "suggestion-not-fit"]].forEach(([label, decision, className]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.addEventListener("click", () => {
        void submitSuggestionDecision(card, jobId, item.group_id, decision === "apply" ? select.value : null, decision);
      });
      actions.append(button);
    });

    const context = contextCells(item.context);
    const decision = document.createElement("div");
    decision.className = "review-decision";
    decision.setAttribute("aria-label", `Решение для «${title.textContent}»`);
    decision.append(
      renderDecisionContext("Выбор", select),
      renderDecisionContext("Эффект", "Только журнал решений"),
      actions,
    );
    card.append(
      header,
      context,
      composition(
        item.candidates.map((candidate) => ({
          title: candidate.label,
          context: { source_unit: candidate.source_unit, confidence: candidate.confidence },
        })),
        item.has_more_candidates,
        "candidate",
      ),
      decision,
    );
    return card;
  };

  const renderDecisionContext = (label, value) => {
    const context = document.createElement("div");
    context.className = "review-decision-context";
    const labelElement = document.createElement("span");
    labelElement.className = "review-decision-label";
    labelElement.textContent = label;
    const valueElement = value instanceof Element ? value : document.createElement("strong");
    if (!(value instanceof Element)) valueElement.textContent = value;
    context.append(labelElement, valueElement);
    return context;
  };

  const renderManualGroup = (item, jobId) => {
    const card = document.createElement("article");
    card.className = "review-item manual-review-card";
    const header = document.createElement("header");
    header.className = "review-item-head";
    const kicker = document.createElement("p");
    kicker.className = "review-kicker";
    kicker.textContent = "Ручное замечание";
    const title = document.createElement("h3");
    title.textContent = suggestionText(item.title, "Нужна ручная проверка");
    const status = document.createElement("p");
    status.className = "decision-status";
    status.textContent = "Требует решения";
    const headerContent = document.createElement("div");
    headerContent.append(kicker, title);
    header.append(headerContent, status);

    const count = Number.isInteger(item.count) && item.count > 0
      ? item.count
      : 0;
    const context = contextCells(item.context, [["reason", item.message], ["member_count", count]]);

    const actions = document.createElement("div");
    actions.className = "review-decision-actions";
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
    const decisionRegion = document.createElement("div");
    decisionRegion.className = "review-decision";
    decisionRegion.setAttribute("aria-label", `Решение для «${title.textContent}»`);
    decisionRegion.append(
      renderDecisionContext("Охват", `Вся группа · ${count} замечаний`),
      renderDecisionContext("Действие", "Одобрить или отклонить"),
      actions,
    );
    card.append(header, context, composition(item.members, item.has_more_members), decisionRegion);
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
    card.querySelectorAll("button, select").forEach((control) => {
      control.disabled = busy;
    });
  };

  const submitSuggestionDecision = async (card, jobId, groupId, suggestionId, decision) => {
    if (typeof jobId !== "string" || !jobId || typeof groupId !== "string") {
      setStatus("Не удалось определить подсказку. Обновите страницу и повторите действие.", true);
      return;
    }
    setSuggestionBusy(card, true);
    try {
      const payload = await requestJson(`/api/jobs/${encodeURIComponent(jobId)}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_id: groupId, suggestion_id: suggestionId, decision }),
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

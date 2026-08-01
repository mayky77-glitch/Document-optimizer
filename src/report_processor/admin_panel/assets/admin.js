(() => {
  "use strict";

  const form = document.querySelector("#job-form");
  const sourceFiles = document.querySelector("#sources");
  const targetFile = document.querySelector("#target");
  const sourceCount = document.querySelector("#source-count");
  const status = document.querySelector("#status");
  const reviewPanel = document.querySelector("#review-panel");
  const reviewState = document.querySelector("#review-state");
  const reviewGroups = document.querySelector("#review-groups");
  const emptyReview = document.querySelector("#empty-review");
  const applyArea = document.querySelector("#review-apply-area");
  const applyButton = document.querySelector("#review-apply");
  const download = document.querySelector("#download");
  const resultHint = document.querySelector("#result-hint");
  const submit = form.querySelector('button[type="submit"]');
  const workbookExtensions = new Set([".xlsx", ".xlsm", ".xlsb"]);
  let currentJobId = "";

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

  const decimalText = (value) => Number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const text = (value, fallback = "—") =>
    typeof value === "string" && value.trim() ? value : fallback;

  const displayNumber = (value, suffix = "") => {
    const number = Number(value);
    return Number.isFinite(number) ? `${decimalText(number)}${suffix}` : "—";
  };

  const reviewCategories = (payload) => Array.isArray(payload.review_categories)
    ? payload.review_categories
      .map((category) => ({
        id: text(category && (category.category_id || category.id), ""),
        label: text(category && (category.label || category.display_name || category.name || category.title), ""),
      }))
      .filter((category) => category.id && category.label)
    : [];

  const reviewGroupsFrom = (payload) => Array.isArray(payload.review_groups)
    ? payload.review_groups.filter((group) => group
      && typeof group.group_id === "string"
      && Number.isInteger(group.version)
      && Array.isArray(group.members))
    : [];

  const groupCategoryId = (group) => text(
    group.selected_category_id || group.category_id || group.proposed_category_id,
    "",
  );

  const groupMode = (group) => group.mode === "cost_only" ? "cost_only" : "quantity_cost";

  const categoryLabel = (categories, id) =>
    categories.find((category) => category.id === id)?.label || "Не выбрана";

  const createCategorySelect = (categories, selectedId, label) => {
    const select = document.createElement("select");
    select.className = "review-category";
    select.setAttribute("aria-label", label);
    const empty = new Option("Выберите категорию", "");
    empty.disabled = true;
    select.append(empty);
    categories.forEach((category) => select.append(new Option(category.label, category.id)));
    select.value = selectedId;
    if (!select.value) select.value = categories[0]?.id || "";
    return select;
  };

  const createModeSwitch = (name, selectedMode, label) => {
    const fieldset = document.createElement("fieldset");
    fieldset.className = "mode-switch";
    const legend = document.createElement("legend");
    legend.textContent = label;
    const options = document.createElement("div");
    options.className = "mode-options";
    [["quantity_cost", "Количество + стоимость"], ["cost_only", "Только стоимость"]].forEach(([value, optionLabel]) => {
      const option = document.createElement("label");
      option.className = "mode-option";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = name;
      input.value = value;
      input.checked = value === selectedMode;
      const visible = document.createElement("span");
      visible.textContent = optionLabel;
      option.append(input, visible);
      options.append(option);
    });
    fieldset.append(legend, options);
    return fieldset;
  };

  const selectedMode = (scope) =>
    scope.querySelector('input[type="radio"]:checked')?.value || "quantity_cost";

  const setReviewBusy = (card, busy) => {
    card.querySelectorAll("button, select, input").forEach((control) => {
      control.disabled = busy;
    });
  };

  const submitReviewDecision = async (card, url, body) => {
    if (!currentJobId || !url) {
      setStatus("Не удалось определить строку для решения. Обновите страницу и повторите действие.", true);
      return;
    }
    setReviewBusy(card, true);
    try {
      const payload = await requestJson(url, {
        method: body ? "PUT" : "DELETE",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      renderJob(payload);
    } catch (error) {
      setReviewBusy(card, false);
      setStatus(error.message, true);
    }
  };

  const decisionBody = (scope, version, action) => {
    if (action === "reject") return { version, action };
    const categoryId = scope.querySelector("select")?.value;
    if (!categoryId) return null;
    return { version, action, category_id: categoryId, mode: selectedMode(scope) };
  };

  const createDecisionActions = (scope, label, submitDecision) => {
    const actions = document.createElement("div");
    actions.className = "review-actions";
    actions.setAttribute("role", "group");
    actions.setAttribute("aria-label", label);
    [["Принять", "accept", "accept"], ["Отклонить", "reject", "reject"]].forEach(([title, action, className]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `review-action ${className}`;
      button.textContent = title;
      button.addEventListener("click", () => {
        const body = decisionBody(scope, Number(scope.dataset.version), action);
        if (!body) {
          setStatus("Выберите целевую категорию перед принятием решения.", true);
          return;
        }
        void submitDecision(body);
      });
      actions.append(button);
    });
    return actions;
  };

  const renderMemberRow = (member, group, categories) => {
    const row = document.createElement("tr");
    const name = text(member && (member.display_name || member.name || member.title), "Строка без названия");
    const version = Number.isInteger(member?.version) ? member.version : group.version;
    [["Работа", name], ["Ед.", text(member?.source_unit)], ["Количество", displayNumber(member?.quantity)], ["Стоимость", displayNumber(member?.cost, " ₽")]].forEach(([label, value]) => {
      const cell = document.createElement("td");
      cell.dataset.label = label;
      cell.textContent = value;
      row.append(cell);
    });
    const controls = document.createElement("td");
    controls.className = "member-controls-cell";
    controls.dataset.label = "Изменение";
    const details = document.createElement("details");
    details.className = "member-override";
    const summary = document.createElement("summary");
    summary.textContent = "Изменить строку";
    const body = document.createElement("div");
    body.className = "member-override-body";
    body.dataset.version = String(version);
    const category = createCategorySelect(
      categories,
      text(member?.category_id || member?.selected_category_id || groupCategoryId(group), ""),
      `Целевая категория для «${name}»`,
    );
    const mode = createModeSwitch(
      `row-${text(member?.row_id, "item")}`,
      member?.mode === "cost_only" ? "cost_only" : groupMode(group),
      "Учесть строку",
    );
    const actions = createDecisionActions(
      body,
      `Решение для строки «${name}»`,
      (decision) => submitReviewDecision(
        row,
        `/api/jobs/${encodeURIComponent(currentJobId)}/review/items/${encodeURIComponent(member.row_id)}`,
        decision,
      ),
    );
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-override";
    remove.textContent = "Убрать изменение";
    remove.addEventListener("click", () => {
      void submitReviewDecision(
        row,
        `/api/jobs/${encodeURIComponent(currentJobId)}/review/items/${encodeURIComponent(member.row_id)}`,
        null,
      );
    });
    body.append(category, mode, actions, remove);
    details.append(summary, body);
    controls.append(details);
    row.append(controls);
    return row;
  };

  const renderGroup = (group, categories) => {
    const card = document.createElement("article");
    card.className = "review-group";
    card.dataset.version = String(group.version);
    const heading = document.createElement("header");
    heading.className = "review-group-head";
    const headingCopy = document.createElement("div");
    const kicker = document.createElement("p");
    kicker.className = "review-kicker";
    kicker.textContent = `Одна группа · ${group.members.length} ${group.members.length === 1 ? "строка" : "строк"}`;
    const title = document.createElement("h3");
    title.textContent = text(group.display_name || group.name || group.title, "Группа строк");
    const proposed = document.createElement("p");
    proposed.className = "proposed-category";
    proposed.textContent = `Предложено: ${categoryLabel(categories, text(group.proposed_category_id, ""))}`;
    headingCopy.append(kicker, title, proposed);
    const chosen = document.createElement("p");
    chosen.className = "chosen-category";
    chosen.textContent = `Выбрано: ${categoryLabel(categories, groupCategoryId(group))}`;
    heading.append(headingCopy, chosen);

    const decision = document.createElement("div");
    decision.className = "group-decision";
    const category = createCategorySelect(categories, groupCategoryId(group), "Целевая категория для группы");
    const categoryField = document.createElement("label");
    categoryField.className = "category-field";
    categoryField.append("Целевая категория", category);
    category.addEventListener("change", () => {
      chosen.textContent = `Выбрано: ${categoryLabel(categories, category.value)}`;
    });
    const mode = createModeSwitch(`group-${group.group_id}`, groupMode(group), "Учесть группу");
    const actions = createDecisionActions(
      card,
      `Решение для группы «${title.textContent}»`,
      (body) => submitReviewDecision(
        card,
        `/api/jobs/${encodeURIComponent(currentJobId)}/review/groups/${encodeURIComponent(group.group_id)}`,
        body,
      ),
    );
    decision.append(categoryField, mode, actions);

    const composition = document.createElement("details");
    composition.className = "review-composition";
    const compositionSummary = document.createElement("summary");
    compositionSummary.textContent = `Все строки группы (${group.members.length})`;
    const table = document.createElement("table");
    const headings = ["Работа", "Ед.", "Количество", "Стоимость", "Изменение"];
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    headings.forEach((label) => {
      const cell = document.createElement("th");
      cell.textContent = label;
      headRow.append(cell);
    });
    head.append(headRow);
    const body = document.createElement("tbody");
    group.members
      .filter((member) => member && typeof member.row_id === "string")
      .forEach((member) => body.append(renderMemberRow(member, group, categories)));
    table.append(head, body);
    composition.append(compositionSummary, table);
    card.append(heading, decision, composition);
    return card;
  };

  const renderReview = (payload) => {
    const categories = reviewCategories(payload);
    const groups = reviewGroupsFrom(payload);
    reviewGroups.replaceChildren(...groups.map((group) => renderGroup(group, categories)));
    const unresolved = Number(payload.unresolved_review_count);
    const unresolvedCount = Number.isInteger(unresolved) && unresolved >= 0 ? unresolved : groups.length;
    reviewState.textContent = unresolvedCount
      ? `Осталось решить: ${unresolvedCount}`
      : payload.review_can_apply === true ? "Все решения готовы к применению." : "Проверка не требует решений.";
    emptyReview.hidden = groups.length !== 0;
    applyArea.hidden = payload.review_can_apply !== true;
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
    currentJobId = typeof payload.job_id === "string" ? payload.job_id : currentJobId;
    renderReview(payload);
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

  applyButton.addEventListener("click", async () => {
    if (!currentJobId) return;
    applyButton.disabled = true;
    try {
      renderJob(await requestJson(`/api/jobs/${encodeURIComponent(currentJobId)}/review/apply`, { method: "POST" }));
    } catch (error) {
      applyButton.disabled = false;
      setStatus(error.message, true);
    }
  });

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

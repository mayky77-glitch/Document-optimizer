(() => {
  "use strict";

  const STORAGE_KEY = "report-processor.reconciliation-batches.job.v1";
  const asArray = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "—") => typeof value === "string" && value.trim() ? value : fallback;
  const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const decimal = (value, suffix = "") => `${number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}${suffix}`;
  const plural = (count, one, few, many = few) => {
    const tail = Math.abs(count) % 100;
    const last = tail % 10;
    return tail > 10 && tail < 20 ? many : last === 1 ? one : last > 1 && last < 5 ? few : many;
  };

  class ReconciliationBatchReview {
    constructor({ root, getJobId, renderPayload, report }) {
      this.root = root;
      this.getJobId = getJobId;
      this.renderPayload = renderPayload;
      this.report = report;
      this.query = "";
      this.filters = window.ReconciliationBatchFilters.defaults();
      this.selectedId = "";
      this.previewingSafe = false;
      this.settledId = "";
      this.handleKeydown = this.handleKeydown.bind(this);
      document.addEventListener("keydown", this.handleKeydown);
    }

    static supports(payload) {
      return Array.isArray(payload?.review_packages);
    }

    static restoredJobId() {
      try {
        return sessionStorage.getItem(STORAGE_KEY) || "";
      } catch {
        return "";
      }
    }

    destroy() {
      document.removeEventListener("keydown", this.handleKeydown);
    }

    categoryLabel(id) {
      return this.categories.find((category) => category.id === id)?.label || "Не выбрана";
    }

    request(url, options = {}) {
      return fetch(url, options)
        .catch(() => { throw new Error("Не удалось связаться с локальной панелью. Повторите действие."); })
        .then(async (response) => {
          let payload;
          try {
            payload = await response.json();
          } catch {
            throw new Error("Панель вернула непонятный ответ. Повторите действие.");
          }
          if (!response.ok) throw new Error(typeof payload?.error === "string" ? payload.error : "Решение не сохранено.");
          return payload;
        });
    }

    saveSession(jobId) {
      try {
        if (jobId) sessionStorage.setItem(STORAGE_KEY, jobId);
      } catch {
        // Session storage is optional. The server remains the autosave authority.
      }
    }

    render(payload) {
      this.payload = payload;
      this.packages = asArray(payload.review_packages).filter((item) => item && typeof item.package_id === "string" && typeof item.version === "string");
      this.categories = asArray(payload.review_categories)
        .map((category) => ({ id: text(category?.category_id || category?.id, ""), label: text(category?.label, "") }))
        .filter((category) => category.id && category.label);
      this.saveSession(text(payload.job_id, this.getJobId()));
      if (!this.packages.some((item) => item.package_id === this.selectedId)) this.selectedId = this.packages[0]?.package_id || "";
      this.root.replaceChildren(this.buildPanel());
    }

    summaryData() {
      const summary = this.payload.review_summary && typeof this.payload.review_summary === "object" ? this.payload.review_summary : {};
      const totals = this.packages.reduce((accumulator, item) => ({
        package_count: accumulator.package_count + 1,
        row_count: accumulator.row_count + number(item.row_count),
        quantity: accumulator.quantity + number(item.quantity),
        cost: accumulator.cost + number(item.cost),
      }), { package_count: 0, row_count: 0, quantity: 0, cost: 0 });
      return { ...totals, ...summary };
    }

    buildPanel() {
      const panel = document.createElement("section");
      panel.className = "batch-review";
      panel.setAttribute("aria-labelledby", "batch-review-title");

      const heading = document.createElement("div");
      heading.className = "batch-heading";
      const title = document.createElement("h3");
      title.id = "batch-review-title";
      title.textContent = "Решения пакетами";
      const explanation = document.createElement("p");
      explanation.textContent = this.payload.review_can_apply === true
        ? "Все решения сохранены. Проверьте последний шаг или примените готовую сверку."
        : "Сначала показаны безопасные пакеты. Одно решение применяется к точному составу семей и групп.";
      heading.append(title, explanation);

      panel.append(heading, this.buildSummary(), this.buildToolbar(), this.buildShortcuts(), this.buildQueue());
      if (this.payload.review_last_action) panel.append(this.buildLastAction());
      return panel;
    }

    buildSummary() {
      const summary = this.summaryData();
      const list = document.createElement("dl");
      list.className = "batch-summary";
      const values = [
        ["Пакеты", String(number(summary.package_count))],
        ["Строки", String(number(summary.row_count))],
        ["Количество", decimal(summary.quantity)],
        ["Стоимость", decimal(summary.cost, " ₽")],
      ];
      values.forEach(([label, value]) => {
        const item = document.createElement("div");
        const term = document.createElement("dt");
        term.textContent = label;
        const detail = document.createElement("dd");
        detail.textContent = value;
        item.append(term, detail);
        list.append(item);
      });
      return list;
    }

    buildToolbar() {
      const toolbar = document.createElement("div");
      toolbar.className = "batch-toolbar";
      toolbar.setAttribute("role", "search");
      const search = document.createElement("input");
      search.type = "search";
      search.className = "batch-search";
      search.placeholder = "Найти пакет или работу";
      search.value = this.query;
      search.setAttribute("aria-label", "Поиск по пакетам");
      search.addEventListener("input", () => {
        this.query = search.value.trim().toLocaleLowerCase("ru-RU");
        this.render(this.payload);
      });
      const filters = window.ReconciliationBatchFilters.build({
        packages: this.packages,
        categories: this.categories,
        state: this.filters,
        onChange: (next) => {
          this.filters = { ...this.filters, ...next };
          this.previewingSafe = false;
          this.render(this.payload);
        },
      });
      toolbar.append(search, filters);
      return toolbar;
    }

    buildShortcuts() {
      const shortcuts = document.createElement("p");
      shortcuts.className = "batch-shortcuts";
      shortcuts.innerHTML = "<span>Клавиши:</span> <kbd>J</kbd>/<kbd>K</kbd> пакет · <kbd>A</kbd> принять · <kbd>R</kbd> отклонить · <kbd>1</kbd>/<kbd>2</kbd> способ учёта · <kbd>U</kbd> отменить";
      return shortcuts;
    }

    visiblePackages() {
      return this.packages.filter((item) => {
        if (!window.ReconciliationBatchFilters.matches(item, this.filters)) return false;
        if (!this.query) return true;
        const haystack = [item.label, item.reason, item.proposed_category_id, item.selected_category_id]
          .concat(asArray(item.families).map((family) => family?.label))
          .join(" ")
          .toLocaleLowerCase("ru-RU");
        return haystack.includes(this.query);
      });
    }

    buildQueue() {
      const area = document.createElement("div");
      area.className = "batch-queue";
      area.setAttribute("aria-live", "polite");
      const filter = window.ReconciliationBatchFilters.primaryFilters
        .find((item) => item.id === this.filters.primary);
      const heading = document.createElement("div");
      heading.className = "batch-queue-heading";
      const title = document.createElement("h4");
      title.textContent = filter?.label || "Пакеты";
      const hint = document.createElement("p");
      hint.textContent = "Можно уточнить выбор дополнительными фильтрами.";
      heading.append(title, hint);
      area.append(heading);
      const items = this.visiblePackages();
      if (this.filters.primary === "safe") area.append(this.buildMassAction(items));
      if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "batch-empty";
        empty.textContent = this.query ? "По этому запросу пакетов нет." : "В этой очереди пакетов нет.";
        area.append(empty);
      }
      items.forEach((item) => area.append(this.buildPackage(item)));
      return area;
    }

    buildMassAction(items) {
      const safe = items.filter((item) => item.safe === true);
      const section = document.createElement("section");
      section.className = "batch-mass-action";
      if (!safe.length) {
        section.hidden = true;
        return section;
      }
      const total = safe.reduce((sum, item) => sum + number(item.cost), 0);
      const copy = document.createElement("p");
      copy.textContent = `${safe.length} ${plural(safe.length, "пакет", "пакета", "пакетов")} без конфликтов · ${decimal(total, " ₽")}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "batch-primary";
      if (this.previewingSafe) {
        button.textContent = `Применить ${safe.length} ${plural(safe.length, "пакет", "пакета", "пакетов")}`;
        button.addEventListener("click", () => this.acceptSafe(safe, button));
      } else {
        button.textContent = "Принять все безопасные";
        button.addEventListener("click", () => {
          this.previewingSafe = true;
          this.render(this.payload);
        });
      }
      section.append(copy, button);
      return section;
    }

    buildPackage(item) {
      const card = document.createElement("article");
      card.className = "batch-package";
      card.tabIndex = 0;
      card.dataset.packageId = item.package_id;
      card.classList.toggle("is-current", item.package_id === this.selectedId);
      card.classList.toggle("is-settled", item.package_id === this.settledId);
      card.addEventListener("focus", () => { this.selectedId = item.package_id; });
      card.addEventListener("click", () => { this.selectedId = item.package_id; });

      const head = document.createElement("header");
      head.className = "batch-package-head";
      const copy = document.createElement("div");
      const queue = document.createElement("p");
      queue.className = "batch-kicker";
      queue.textContent = `${number(item.family_count)} ${plural(number(item.family_count), "семейство", "семейства", "семейств")} · ${number(item.exception_count)} ${plural(number(item.exception_count), "исключение", "исключения", "исключений")}`;
      const title = document.createElement("h5");
      title.textContent = text(item.label, "Пакет работ");
      const proposed = document.createElement("p");
      proposed.className = "batch-proposed";
      proposed.textContent = `Предложено: ${this.categoryLabel(text(item.proposed_category_id, ""))}`;
      copy.append(queue, title, proposed);
      const status = document.createElement("span");
      status.className = "batch-status";
      status.textContent = item.package_id === this.settledId ? "Готово" : item.safe === true ? "Можно принять" : "Проверьте";
      head.append(copy, status);

      const totals = document.createElement("dl");
      totals.className = "batch-totals";
      [["Группы", number(item.group_count)], ["Строки", number(item.row_count)], ["Количество", decimal(item.quantity)], ["Стоимость", decimal(item.cost, " ₽")]].forEach(([label, value]) => {
        const row = document.createElement("div");
        row.innerHTML = `<dt>${label}</dt><dd>${value}</dd>`;
        totals.append(row);
      });
      const reason = document.createElement("p");
      reason.className = "batch-reason";
      reason.textContent = text(item.reason, "Причина не указана.");
      card.append(head, totals, reason, this.buildDecision(item), this.buildFamilies(item));
      return card;
    }

    buildDecision(item) {
      const decision = document.createElement("div");
      decision.className = "batch-decision";
      const categoryLabel = document.createElement("label");
      categoryLabel.textContent = "Категория";
      const category = document.createElement("select");
      category.className = "batch-category";
      category.setAttribute("aria-label", `Категория для пакета «${text(item.label)}»`);
      this.categories.forEach((entry) => category.append(new Option(entry.label, entry.id)));
      category.value = text(item.selected_category_id || item.proposed_category_id, "");
      categoryLabel.append(category);
      const mode = this.buildMode(`package-${item.package_id}`, item.mode, `Способ учёта пакета «${text(item.label)}»`);
      const actions = document.createElement("div");
      actions.className = "batch-actions";
      const accept = this.actionButton("Принять пакет", "accept", () => this.savePackage(item, category.value, this.modeOf(mode), "accept", decision));
      const reject = this.actionButton("Отклонить", "reject", () => this.savePackage(item, category.value, this.modeOf(mode), "reject", decision));
      actions.append(accept, reject);
      decision.append(categoryLabel, mode, actions);
      return decision;
    }

    buildMode(name, selected, label) {
      const fieldset = document.createElement("fieldset");
      fieldset.className = "batch-mode";
      const legend = document.createElement("legend");
      legend.textContent = label;
      const options = document.createElement("div");
      options.className = "batch-mode-options";
      [["quantity_cost", "Количество + стоимость"], ["cost_only", "Только стоимость"]].forEach(([value, caption]) => {
        const option = document.createElement("label");
        const input = document.createElement("input");
        input.type = "radio";
        input.name = name;
        input.value = value;
        input.checked = (selected === "cost_only" ? "cost_only" : "quantity_cost") === value;
        const visible = document.createElement("span");
        visible.textContent = caption;
        option.append(input, visible);
        options.append(option);
      });
      fieldset.append(legend, options);
      return fieldset;
    }

    modeOf(scope) {
      return scope.querySelector('input[type="radio"]:checked')?.value || "quantity_cost";
    }

    actionButton(label, kind, handler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `batch-action ${kind}`;
      button.textContent = label;
      button.addEventListener("click", handler);
      return button;
    }

    buildFamilies(item) {
      const details = document.createElement("details");
      details.className = "batch-families";
      const summary = document.createElement("summary");
      const families = asArray(item.families);
      summary.textContent = `Точный состав: ${families.length} ${plural(families.length, "семейство", "семейства", "семейств")}`;
      const body = document.createElement("div");
      body.className = "batch-family-list";
      families.forEach((family) => body.append(this.buildFamily(family)));
      details.append(summary, body);
      return details;
    }

    buildFamily(family) {
      const details = document.createElement("details");
      details.className = "batch-family";
      const summary = document.createElement("summary");
      summary.textContent = `${text(family?.label, "Семейство работ")} · ${asArray(family?.groups).length} ${plural(asArray(family?.groups).length, "группа", "группы", "групп")}`;
      const body = document.createElement("div");
      body.className = "batch-family-body";
      const groups = asArray(family?.groups);
      groups.forEach((group) => body.append(this.buildGroup(family, group)));
      details.append(summary, body);
      return details;
    }

    buildGroup(family, group) {
      const details = document.createElement("details");
      details.className = "batch-group";
      const summary = document.createElement("summary");
      const members = asArray(group?.members);
      summary.textContent = `${text(group?.label || group?.display_name || group?.name, "Группа строк")} · ${members.length} ${plural(members.length, "строка", "строки", "строк")}`;
      const body = document.createElement("div");
      body.className = "batch-group-body";
      body.append(this.buildFamilyActions(family, group));
      body.append(this.buildGroupActions(group));
      const rows = document.createElement("ul");
      rows.className = "batch-rows";
      members.forEach((member) => {
        const row = document.createElement("li");
        const title = document.createElement("span");
        title.textContent = `${text(member?.display_name || member?.name || member?.title, "Строка без названия")} · ${decimal(member?.quantity)} · ${decimal(member?.cost, " ₽")}`;
        row.append(title, this.buildRowActions(member, group));
        rows.append(row);
      });
      body.append(rows);
      details.append(summary, body);
      return details;
    }

    buildFamilyActions(family, group) {
      const section = document.createElement("div");
      section.className = "batch-family-actions";
      const label = document.createElement("span");
      label.textContent = "Для всего семейства";
      const category = document.createElement("select");
      this.categories.forEach((entry) => category.append(new Option(entry.label, entry.id)));
      category.value = text(family?.selected_category_id || family?.proposed_category_id || this.payload.review_categories?.[0]?.category_id, "");
      const mode = this.buildMode(`family-${text(family?.family_id, "family")}`, family?.mode, "Способ учёта семейства");
      const accept = this.actionButton("Принять семейство", "accept", () => this.saveFamily(family, category.value, this.modeOf(mode), "accept", section));
      const reject = this.actionButton("Отклонить семейство", "reject", () => this.saveFamily(family, category.value, this.modeOf(mode), "reject", section));
      section.append(label, category, mode, accept, reject);
      return section;
    }

    buildGroupActions(group) {
      const section = document.createElement("div");
      section.className = "batch-scope-actions";
      const label = document.createElement("span");
      label.textContent = "Для всей группы";
      const category = document.createElement("select");
      this.categories.forEach((entry) => category.append(new Option(entry.label, entry.id)));
      category.value = text(group?.selected_category_id || group?.proposed_category_id, "");
      const mode = this.buildMode(`group-${text(group?.group_id, "group")}`, group?.mode, "Способ учёта группы");
      const accept = this.actionButton("Принять группу", "accept", () => this.saveGroup(group, category.value, this.modeOf(mode), "accept", section));
      const reject = this.actionButton("Отклонить группу", "reject", () => this.saveGroup(group, category.value, this.modeOf(mode), "reject", section));
      section.append(label, category, mode, accept, reject);
      return section;
    }

    buildRowActions(member, group) {
      const details = document.createElement("details");
      details.className = "batch-row-actions";
      const summary = document.createElement("summary");
      summary.textContent = "Изменить строку";
      const body = document.createElement("div");
      const category = document.createElement("select");
      category.setAttribute("aria-label", `Категория для строки «${text(member?.display_name || member?.name)}»`);
      this.categories.forEach((entry) => category.append(new Option(entry.label, entry.id)));
      category.value = text(member?.selected_category_id || member?.category_id || group?.selected_category_id || group?.proposed_category_id, "");
      const mode = this.buildMode(`row-${text(member?.row_id, "row")}`, member?.mode || group?.mode, "Способ учёта строки");
      const accept = this.actionButton("Принять строку", "accept", () => this.saveItem(member, group, category.value, this.modeOf(mode), "accept", body));
      const reject = this.actionButton("Отклонить строку", "reject", () => this.saveItem(member, group, category.value, this.modeOf(mode), "reject", body));
      body.append(category, mode, accept, reject);
      details.append(summary, body);
      return details;
    }

    setBusy(scope, busy) {
      scope?.querySelectorAll("button, select, input").forEach((control) => { control.disabled = busy; });
    }

    async savePackage(item, categoryId, mode, action, scope) {
      const jobId = this.getJobId();
      if (!jobId) return this.report("Не удалось восстановить сверку. Обновите страницу.", true);
      const resolvedAction = action === "reject" ? "reject" : categoryId === item.proposed_category_id ? "accept" : "change_category";
      const body = action === "reject"
        ? { version: item.version, action: resolvedAction }
        : { version: item.version, action: resolvedAction, category_id: categoryId, mode };
      this.setBusy(scope, true);
      try {
        this.settledId = item.package_id;
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/packages/${encodeURIComponent(item.package_id)}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        }));
      } catch (error) {
        this.setBusy(scope, false);
        this.report(error.message, true);
      }
    }

    async saveFamily(family, categoryId, mode, action, scope) {
      const jobId = this.getJobId();
      if (!jobId || typeof family?.family_id !== "string") return this.report("Не удалось определить семейство. Обновите страницу.", true);
      const resolvedAction = action === "reject" ? "reject" : categoryId === family.proposed_category_id ? "accept" : "change_category";
      const body = action === "reject"
        ? { version: family.version, action: resolvedAction }
        : { version: family.version, action: resolvedAction, category_id: categoryId, mode };
      this.setBusy(scope, true);
      try {
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/families/${encodeURIComponent(family.family_id)}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        }));
      } catch (error) {
        this.setBusy(scope, false);
        this.report(error.message, true);
      }
    }

    async saveGroup(group, categoryId, mode, action, scope) {
      const jobId = this.getJobId();
      if (!jobId || typeof group?.group_id !== "string") return this.report("Не удалось определить группу. Обновите страницу.", true);
      const resolvedAction = action === "reject" ? "reject" : categoryId === group.proposed_category_id ? "accept" : "change_category";
      const body = action === "reject"
        ? { version: group.version, action: resolvedAction }
        : { version: group.version, action: resolvedAction, category_id: categoryId, mode };
      this.setBusy(scope, true);
      try {
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/groups/${encodeURIComponent(group.group_id)}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        }));
      } catch (error) {
        this.setBusy(scope, false);
        this.report(error.message, true);
      }
    }

    async saveItem(member, group, categoryId, mode, action, scope) {
      const jobId = this.getJobId();
      if (!jobId || typeof member?.row_id !== "string") return this.report("Не удалось определить строку. Обновите страницу.", true);
      const resolvedAction = action === "reject" ? "reject" : categoryId === group?.proposed_category_id ? "accept" : "change_category";
      const body = action === "reject"
        ? { version: text(member.version || group?.version, ""), action: resolvedAction }
        : { version: text(member.version || group?.version, ""), action: resolvedAction, category_id: categoryId, mode };
      this.setBusy(scope, true);
      try {
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/items/${encodeURIComponent(member.row_id)}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
        }));
      } catch (error) {
        this.setBusy(scope, false);
        this.report(error.message, true);
      }
    }

    async acceptSafe(packages, scope) {
      const jobId = this.getJobId();
      if (!jobId) return this.report("Не удалось восстановить сверку. Обновите страницу.", true);
      this.setBusy(scope.parentElement, true);
      try {
        const frozen = packages.map((item) => ({ package_id: item.package_id, version: item.version }));
        this.previewingSafe = false;
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/packages/accept-safe`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ packages: frozen }),
        }));
      } catch (error) {
        this.setBusy(scope.parentElement, false);
        this.report(error.message, true);
      }
    }

    buildLastAction() {
      const section = document.createElement("section");
      section.className = "batch-last-action";
      const copy = document.createElement("p");
      copy.textContent = this.lastActionText();
      const undo = document.createElement("button");
      undo.type = "button";
      undo.className = "batch-undo";
      undo.textContent = "Отменить последнее решение";
      undo.addEventListener("click", () => this.undo(undo));
      section.append(copy, undo);
      return section;
    }

    lastActionText() {
      const action = this.payload.review_last_action;
      if (typeof action === "string") return text(action, "Последнее решение можно отменить.");
      if (action && typeof action === "object") {
        return text(action.label || action.message || action.description, "Последнее решение можно отменить.");
      }
      return "Последнее решение можно отменить.";
    }

    async undo(scope) {
      const jobId = this.getJobId();
      if (!jobId) return;
      this.setBusy(scope.parentElement, true);
      try {
        this.renderPayload(await this.request(`/api/jobs/${encodeURIComponent(jobId)}/review/undo`, { method: "POST" }));
      } catch (error) {
        this.setBusy(scope.parentElement, false);
        this.report(error.message, true);
      }
    }

    currentCard() {
      return this.root.querySelector(`.batch-package[data-package-id="${CSS.escape(this.selectedId)}"]`);
    }

    handleKeydown(event) {
      if (!this.payload || event.altKey || event.ctrlKey || event.metaKey || event.isComposing) return;
      if (event.target.matches("input, select, textarea, button")) return;
      const cards = [...this.root.querySelectorAll(".batch-package")];
      const active = this.currentCard();
      if (event.key.toLowerCase() === "j" || event.key.toLowerCase() === "k") {
        if (!cards.length) return;
        event.preventDefault();
        const index = Math.max(0, cards.indexOf(active));
        const next = cards[Math.min(cards.length - 1, Math.max(0, index + (event.key.toLowerCase() === "j" ? 1 : -1)))];
        this.selectedId = next.dataset.packageId;
        next.focus({ preventScroll: false });
        return;
      }
      if (event.key.toLowerCase() === "u") {
        const undo = this.root.querySelector(".batch-undo");
        if (undo) { event.preventDefault(); undo.click(); }
        return;
      }
      if (!active) return;
      if (event.key.toLowerCase() === "a" || event.key.toLowerCase() === "r") {
        event.preventDefault();
        active.querySelector(`.batch-action.${event.key.toLowerCase() === "a" ? "accept" : "reject"}`)?.click();
      }
      if (event.key === "1" || event.key === "2") {
        event.preventDefault();
        active.querySelector(`input[value="${event.key === "1" ? "quantity_cost" : "cost_only"}"]`)?.click();
      }
    }
  }

  window.ReconciliationBatchReview = ReconciliationBatchReview;
})();

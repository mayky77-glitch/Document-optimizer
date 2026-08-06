(() => {
  "use strict";

  const PAGE_SIZE = 20;
  const SESSION_KEY_PREFIX = "report-processor.drawing-card.review.v2";
  const quantityFormat = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const text = (value, fallback = "Не указано") =>
    typeof value === "string" && value.trim()
      ? value
      : typeof value === "number"
        ? String(value)
        : fallback;

  const numberText = (value, fallback = "—") => {
    const number = Number(value);
    return Number.isFinite(number) ? quantityFormat.format(number) : fallback;
  };

  const decisionLabel = (value) => ({
    approved: "Одобрено",
    rejected: "Отклонено",
    excluded: "Исключено из пакета",
    exclude: "Исключено из пакета",
    cost_only: "Учтена только стоимость",
    change_category: "Категория изменена",
    pending: "Ожидает решения",
    unresolved: "Ожидает решения",
  }[value] || "Ожидает решения");

  const firstValue = (source, keys) => {
    if (!source || typeof source !== "object") return undefined;
    for (const key of keys) {
      if (source[key] !== null && source[key] !== undefined) return source[key];
    }
    return undefined;
  };

  const categoriesFrom = (payload) => Array.isArray(payload?.review_categories)
    ? payload.review_categories.map((category) => ({
      id: text(firstValue(category, ["id", "category_id"]), ""),
      label: text(firstValue(category, ["label", "display_name", "name"]), ""),
      units: Array.isArray(category?.units) ? category.units.filter((unit) => typeof unit === "string") : [],
    })).filter((category) => category.id && category.label)
    : [];

  class DrawingCardReviewPanel {
    constructor({ requestJson, setStatus, setProgress, renderResult, persistSession, renderJob }) {
      this.requestJson = requestJson;
      this.setStatus = setStatus;
      this.setProgress = setProgress;
      this.renderResult = renderResult;
      this.persistSession = persistSession;
      this.renderJob = renderJob;
      this.panel = document.querySelector("#review-panel");
      this.summary = document.querySelector("#summary");
      this.items = document.querySelector("#review-items");
      this.empty = document.querySelector("#review-empty");
      this.hint = document.querySelector("#review-hint");
      this.applyButton = document.querySelector("#apply-review");
      this.pagination = document.querySelector("#review-pagination");
      this.previous = document.querySelector("#previous-page");
      this.next = document.querySelector("#next-page");
      this.pageStatus = document.querySelector("#page-status");
      this.legacy = document.querySelector("#legacy-review");
      this.reviewDownload = document.querySelector("#review-download");
      this.reviewForm = document.querySelector("#review-form");
      this.submitReview = document.querySelector("#submit-review");
      this.filtersForm = document.querySelector("#review-filters");
      this.reasonFilter = document.querySelector("#review-filter-reason");
      this.categoryFilter = document.querySelector("#review-filter-category");
      this.filenameFilter = document.querySelector("#review-filter-filename");
      this.confidenceFilter = document.querySelector("#review-filter-confidence");
      this.onlyUnresolvedFilter = document.querySelector("#review-filter-only-unresolved");
      this.resetFilters = document.querySelector("#reset-review-filters");
      this.mobileBar = document.querySelector("#review-mobile-bar");
      this.mobileCount = document.querySelector("#review-mobile-count");
      this.mobileNext = document.querySelector("#review-mobile-next");
      this.jobId = null;
      this.page = 1;
      this.totalPages = 1;
      this.categories = [];
      this.filters = this.defaultFilters();
      this.expandedMembers = new Set();
      this.previous.addEventListener("click", () => this.load(this.page - 1, true));
      this.next.addEventListener("click", () => this.load(this.page + 1, true));
      this.applyButton.addEventListener("click", () => this.apply());
      this.reviewForm.addEventListener("submit", (event) => this.uploadLegacy(event));
      this.filtersForm.addEventListener("submit", (event) => {
        event.preventDefault();
        this.filters = this.readFilters();
        this.saveReviewSession();
        void this.load(1, true);
      });
      this.resetFilters.addEventListener("click", () => {
        this.filters = this.defaultFilters();
        this.writeFilters();
        this.saveReviewSession();
        void this.load(1, true);
      });
      this.onlyUnresolvedFilter.addEventListener("change", () => {
        this.filters.onlyUnresolved = this.onlyUnresolvedFilter.checked;
        this.saveReviewSession();
      });
      this.mobileNext.addEventListener("click", () => this.loadNextUnresolved());
    }

    defaultFilters() {
      return { reason: "", category: "", filename: "", confidence: "", onlyUnresolved: true };
    }

    reviewSessionKey() {
      return this.jobId ? `${SESSION_KEY_PREFIX}.${this.jobId}` : SESSION_KEY_PREFIX;
    }

    restoreReviewSession(fallbackPage) {
      let saved = null;
      try {
        saved = JSON.parse(sessionStorage.getItem(this.reviewSessionKey()) || "null");
      } catch {
        // Storage is optional; the review starts with safe unresolved filtering.
      }
      this.filters = { ...this.defaultFilters(), ...(saved?.filters || {}) };
      this.filters.onlyUnresolved = this.filters.onlyUnresolved !== false;
      this.expandedMembers = new Set(Array.isArray(saved?.expandedMembers) ? saved.expandedMembers : []);
      this.page = Number(saved?.page) > 0 ? Number(saved.page) : fallbackPage;
      this.writeFilters();
    }

    saveReviewSession() {
      try {
        sessionStorage.setItem(this.reviewSessionKey(), JSON.stringify({
          filters: this.filters,
          page: this.page,
          expandedMembers: [...this.expandedMembers],
        }));
      } catch {
        // Browser storage is optional.
      }
      this.persistSession("review", this.page);
    }

    readFilters() {
      return {
        reason: this.reasonFilter.value.trim(),
        category: this.categoryFilter.value,
        filename: this.filenameFilter.value.trim(),
        confidence: this.confidenceFilter.value,
        onlyUnresolved: this.onlyUnresolvedFilter.checked,
      };
    }

    writeFilters() {
      this.reasonFilter.value = this.filters.reason;
      this.categoryFilter.value = this.filters.category;
      this.filenameFilter.value = this.filters.filename;
      this.confidenceFilter.value = this.filters.confidence;
      this.onlyUnresolvedFilter.checked = this.filters.onlyUnresolved;
    }

    async show(payload, jobId, page = 1) {
      const isNewJob = this.jobId !== jobId;
      this.jobId = jobId;
      if (isNewJob) this.restoreReviewSession(page);
      this.panel.hidden = false;
      this.legacy.hidden = true;
      this.items.hidden = false;
      this.filtersForm.hidden = false;
      this.applyButton.hidden = false;
      this.mobileBar.hidden = false;
      this.setProgress("review");
      try {
        await this.load(this.page || page);
        this.panel.focus({ preventScroll: true });
      } catch (error) {
        if (payload.review_url || payload.can_upload_review) {
          this.showLegacy(payload);
          return;
        }
        throw error;
      }
    }

    hide() {
      this.panel.hidden = true;
    }

    endpoint(clusterId = "") {
      const path = `/api/drawing-card/jobs/${encodeURIComponent(this.jobId)}/review/clusters`;
      return clusterId ? `${path}/${encodeURIComponent(clusterId)}` : path;
    }

    itemEndpoint(reviewId) {
      return `/api/drawing-card/jobs/${encodeURIComponent(this.jobId)}/review/items/${encodeURIComponent(reviewId)}`;
    }

    queryFor(page) {
      const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      query.set("only_unresolved", String(this.filters.onlyUnresolved));
      [["reason", this.filters.reason], ["category", this.filters.category], ["safe_filename", this.filters.filename], ["confidence", this.filters.confidence]]
        .forEach(([key, value]) => {
          if (value) query.set(key, value);
        });
      return query;
    }

    async load(page = 1, moveFocus = false) {
      if (!this.jobId) return;
      const payload = await this.requestJson(`${this.endpoint()}?${this.queryFor(page)}`, { method: "GET" });
      this.render(payload);
      if (moveFocus) this.focusNextVisiblePacket();
    }

    render(payload) {
      const clusters = Array.isArray(payload.packets)
        ? payload.packets
        : Array.isArray(payload.clusters)
          ? payload.clusters
          : Array.isArray(payload.items)
            ? payload.items
            : [];
      const categories = categoriesFrom(payload);
      if (categories.length) this.categories = categories;
      this.renderCategoryFilter();
      this.items.replaceChildren(...clusters.map((cluster) => this.renderCluster(cluster)));
      this.empty.hidden = clusters.length !== 0;
      this.page = Number(payload.page) || this.page;
      const total = Number(payload.total_packets ?? payload.total_clusters) || clusters.length;
      this.totalPages = Math.max(1, Math.ceil(total / (Number(payload.page_size) || PAGE_SIZE)));
      this.pagination.hidden = this.totalPages <= 1;
      this.previous.disabled = this.page <= 1;
      this.next.disabled = this.page >= this.totalPages;
      this.pageStatus.textContent = `Страница ${this.page} из ${this.totalPages} · пакетов: ${new Intl.NumberFormat("ru-RU").format(total)}`;
      this.renderSummary(payload);
      const unresolvedPackets = Number(payload.unresolved_packets ?? payload.unresolved_clusters);
      const unresolvedRows = Number(payload.unresolved_rows);
      const pending = Number.isFinite(unresolvedPackets) ? unresolvedPackets : total;
      this.applyButton.disabled = pending > 0 || payload.can_apply === false;
      this.hint.textContent = this.applyButton.disabled
        ? `Осталось решить: пакетов — ${new Intl.NumberFormat("ru-RU").format(pending)}, строк — ${Number.isFinite(unresolvedRows) ? new Intl.NumberFormat("ru-RU").format(unresolvedRows) : "не указано"}.`
        : "Все пакеты обработаны. Примените решения, чтобы собрать отчёт.";
      this.mobileBar.hidden = false;
      this.mobileCount.textContent = `Осталось: ${new Intl.NumberFormat("ru-RU").format(pending)}`;
      this.mobileNext.disabled = pending === 0;
      this.saveReviewSession();
    }

    renderCategoryFilter() {
      const selected = this.filters.category;
      this.categoryFilter.replaceChildren(new Option("Все категории", ""));
      this.categories.forEach((category) => {
        const suffix = category.units.length ? ` · ${category.units.join(", ")}` : "";
        this.categoryFilter.append(new Option(`${category.label}${suffix}`, category.id));
      });
      this.categoryFilter.value = selected;
    }

    renderSummary(payload) {
      const pairs = [
        ["Необработанные пакеты", payload.unresolved_packets ?? payload.unresolved_clusters],
        ["Строки в необработанных пакетах", payload.unresolved_rows],
        ["Всего пакетов", payload.total_packets ?? payload.total_clusters],
        ["Всего строк", payload.total_rows],
      ];
      this.summary.replaceChildren(...pairs
        .filter(([, value]) => Number.isFinite(Number(value)))
        .map(([label, value]) => {
          const item = document.createElement("span");
          item.textContent = `${label}: ${new Intl.NumberFormat("ru-RU").format(Number(value))}`;
          return item;
        }));
    }

    categoryLabel(id, label) {
      return text(label, this.categories.find((category) => category.id === id)?.label || "Не указана");
    }

    packetLabel(cluster, count) {
      if (cluster.hazard === true || cluster.is_hazard === true || cluster.packet_type === "hazard") return "Опасная строка · отдельная проверка";
      if (cluster.singleton === true || cluster.is_singleton === true || count === 1) return "Одиночная строка";
      return "Пакет строк";
    }

    renderCluster(cluster) {
      const article = document.createElement("article");
      article.className = "review-item review-cluster";
      const id = text(firstValue(cluster, ["packet_id", "cluster_id"]), "");
      const version = text(cluster.version, "");
      const members = Array.isArray(cluster.members) ? cluster.members : [];
      const count = Number(cluster.member_count) || members.length;
      const selected = text(cluster.selected_category, "");
      const proposed = text(cluster.proposed_category, "");
      const decision = text(cluster.decision, "unresolved");
      const resolved = ["approved", "rejected", "excluded", "cost_only", "change_category"].includes(decision);
      article.dataset.clusterId = id;
      article.dataset.unresolved = String(!resolved);
      if (cluster.hazard === true || cluster.is_hazard === true || cluster.packet_type === "hazard") article.classList.add("is-hazard");
      article.innerHTML = `
        <header class="review-item-head">
          <div>
            <p class="review-kicker"></p>
            <h3></h3>
          </div>
          <p class="decision-status"></p>
        </header>
        <dl class="review-context review-cluster-context">
          <div><dt>Ед. в источнике</dt><dd data-field="source-unit"></dd></div>
          <div><dt>Ед. в цели</dt><dd data-field="target-unit"></dd></div>
          <div><dt>Предложенная категория</dt><dd data-field="proposed"></dd></div>
          <div><dt>Уверенность</dt><dd data-field="confidence"></dd></div>
          <div><dt>Объяснение уверенности</dt><dd data-field="confidence-explanation"></dd></div>
          <div><dt>Причина проверки</dt><dd data-field="reason"></dd></div>
          <div><dt>Стоимость пакета</dt><dd class="aggregate-cost" data-field="aggregate-cost"></dd></div>
        </dl>
        <p class="selected-category" hidden></p>
        <div class="item-actions" aria-label="Решение по пакету строк"></div>
        <div class="review-decision" aria-label="Выберите решение для пакета строк">
          <label>Категория<select class="category-input"></select></label>
          <fieldset class="review-mode">
            <legend>Учитывать</legend>
            <div class="segmented-control" role="group" aria-label="Режим учёта">
              <button type="button" class="is-selected" data-review-mode="full" aria-pressed="true">Количество + стоимость</button>
              <button type="button" data-review-mode="cost_only" aria-pressed="false">Только стоимость</button>
            </div>
          </fieldset>
          <div class="review-decision-actions">
            <button type="button" class="apply-cluster-action approve-action">Применить</button>
            <button type="button" class="reject-cluster-action danger-action">Отклонить</button>
          </div>
        </div>`;
      article.querySelector(".review-kicker").textContent = `${this.packetLabel(cluster, count)} · строк: ${new Intl.NumberFormat("ru-RU").format(count)}`;
      article.querySelector("h3").textContent = text(cluster.work_name, "Наименование работы не указано");
      article.querySelector(".decision-status").textContent = decisionLabel(decision);
      article.querySelector('[data-field="source-unit"]').textContent = text(cluster.source_unit);
      article.querySelector('[data-field="target-unit"]').textContent = text(cluster.target_unit);
      article.querySelector('[data-field="proposed"]').textContent = this.categoryLabel(proposed, cluster.proposed_category_label);
      article.querySelector('[data-field="confidence"]').textContent = Number.isFinite(Number(cluster.confidence))
        ? `${Math.round(Number(cluster.confidence) * 100)}%`
        : "Не указана";
      article.querySelector('[data-field="confidence-explanation"]').textContent = text(firstValue(cluster, ["confidence_explanation", "confidence_label"]));
      article.querySelector('[data-field="reason"]').textContent = text(firstValue(cluster, ["reason_label", "reason_display", "reason"]));
      article.querySelector('[data-field="aggregate-cost"]').textContent = numberText(firstValue(cluster, ["aggregate_total_cost", "total_cost"]));
      article.querySelector(".review-context").after(this.renderMembers(members, count, id));
      const selectedLabel = article.querySelector(".selected-category");
      if (selected) {
        selectedLabel.hidden = false;
        selectedLabel.textContent = `Принятая категория: ${this.categoryLabel(selected, cluster.selected_category_label)}`;
      }
      this.configureActions(article, { id, version, resolved, decision, proposed });
      return article;
    }

    renderMembers(members, count, clusterId) {
      const details = document.createElement("details");
      details.className = "cluster-members";
      details.open = this.expandedMembers.has(clusterId);
      const summary = document.createElement("summary");
      summary.textContent = `Строк в пакете: ${new Intl.NumberFormat("ru-RU").format(count)}. Показать состав`;
      const explanation = document.createElement("p");
      explanation.textContent = `Решение ниже применяется ко всем ${new Intl.NumberFormat("ru-RU").format(count)} строкам пакета, пока строка не исключена отдельно.`;
      details.addEventListener("toggle", () => {
        if (details.open) this.expandedMembers.add(clusterId);
        else this.expandedMembers.delete(clusterId);
        this.saveReviewSession();
      });
      details.append(summary, explanation);

      if (!members.length) {
        const empty = document.createElement("p");
        empty.className = "cluster-members-empty";
        empty.textContent = "Состав пакета не получен.";
        details.append(empty);
        return details;
      }

      const warning = document.createElement("p");
      warning.className = "member-override-warning";
      warning.textContent = "Исключение строки прекращает действие решения пакета только для этой строки. Проверьте её отдельно.";
      const scroll = document.createElement("div");
      scroll.className = "cluster-members-table-wrap";
      scroll.tabIndex = 0;
      scroll.setAttribute("aria-label", "Таблица состава пакета строк; для просмотра используйте горизонтальную прокрутку");
      const table = document.createElement("table");
      table.className = "cluster-members-table";
      const caption = document.createElement("caption");
      caption.textContent = "Состав пакета строк";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      ["Файл", "Лист", "Строка", "Позиция", "Шифр", "Наименование", "Ед.", "Количество", "Стоимость", "Уверенность", "Причина", "Действие"].forEach((label) => {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = label;
        headRow.append(cell);
      });
      head.append(headRow);
      const body = document.createElement("tbody");
      members.forEach((member) => body.append(this.renderMember(member)));
      table.append(caption, head, body);
      scroll.append(table);
      details.append(warning, scroll);
      return details;
    }

    renderMember(member) {
      const row = document.createElement("tr");
      const reviewId = text(firstValue(member, ["review_id", "member_id", "row_id"]), "");
      const values = [
        text(firstValue(member, ["safe_filename", "filename", "source_basename"]), "—"),
        text(firstValue(member, ["sheet_name", "sheet"]), "—"),
        text(firstValue(member, ["row_number", "row"]), "—"),
        text(firstValue(member, ["position", "position_code"]), "—"),
        text(firstValue(member, ["drawing_code", "drawing"]), "—"),
        text(firstValue(member, ["work_name", "name", "display_name"]), "Не указано"),
        text(firstValue(member, ["source_unit", "unit"]), "—"),
        numberText(firstValue(member, ["quantity", "remaining_quantity"])),
        numberText(firstValue(member, ["total_cost", "cost", "remaining_total_cost"])),
        Number.isFinite(Number(member.confidence)) ? `${Math.round(Number(member.confidence) * 100)}%` : "—",
        text(firstValue(member, ["reason_label", "reason_display", "reason"]), "—"),
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (index === 5) cell.className = "member-name";
        if (index === 8) cell.className = "member-cost";
        row.append(cell);
      });
      const actionCell = document.createElement("td");
      actionCell.append(this.memberOverride(member, reviewId));
      row.append(actionCell);
      return row;
    }

    memberOverride(member, reviewId) {
      const details = document.createElement("details");
      details.className = "member-override";
      const summary = document.createElement("summary");
      summary.textContent = "Изменить строку";
      const label = document.createElement("label");
      label.textContent = "Категория";
      const category = document.createElement("select");
      category.append(new Option("Выберите категорию", ""));
      this.categories.forEach((item) => category.append(new Option(item.label, item.id)));
      category.value = text(firstValue(member, ["selected_category", "proposed_category"]), "");
      label.append(category);
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = "Сохранить строку";
      save.addEventListener("click", () => {
        if (!category.value) {
          category.focus();
          return;
        }
        void this.saveMember(details, reviewId, member.version, "change_category", category.value);
      });
      const exclude = document.createElement("button");
      exclude.type = "button";
      exclude.className = "danger-action";
      exclude.textContent = "Исключить из пакета";
      exclude.addEventListener("click", () => void this.saveMember(details, reviewId, member.version, "exclude"));
      details.append(summary, label, save, exclude);
      return details;
    }

    configureActions(article, state) {
      const actions = article.querySelector(".item-actions");
      const decision = article.querySelector(".review-decision");
      const category = article.querySelector(".category-input");
      category.append(new Option("Выберите категорию", ""));
      this.categories.forEach((item) => category.append(new Option(item.label, item.id)));
      category.value = state.proposed;
      const addAction = (label, action, style = "") => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        if (style) button.className = style;
        button.addEventListener("click", () => this.save(article, state.id, state.version, action));
        actions.append(button);
      };
      if (state.resolved) {
        addAction("Отменить решение", "undo");
        decision.hidden = true;
      } else {
        let mode = "full";
        const modeButtons = decision.querySelectorAll("[data-review-mode]");
        modeButtons.forEach((button) => {
          button.addEventListener("click", () => {
            mode = button.dataset.reviewMode;
            modeButtons.forEach((control) => {
              const selected = control === button;
              control.classList.toggle("is-selected", selected);
              control.setAttribute("aria-pressed", String(selected));
            });
          });
        });
        decision.querySelector(".apply-cluster-action").addEventListener("click", () => {
          if (!category.value) {
            category.focus();
            return;
          }
          const action = mode === "cost_only"
            ? "cost_only"
            : category.value === state.proposed ? "approve" : "change_category";
          this.save(article, state.id, state.version, action, action === "approve" ? undefined : category.value);
        });
        decision.querySelector(".reject-cluster-action").addEventListener("click", () => {
          this.save(article, state.id, state.version, "reject");
        });
      }
    }

    async save(article, id, version, action, category) {
      if (!id || !version) {
        this.setStatus("Не удалось определить пакет проверки. Обновите страницу и повторите действие.", true);
        return;
      }
      this.setBusy(article, true);
      try {
        if (action === "undo") {
          await this.requestJson(this.endpoint(id), {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version }),
          });
        } else {
          const payload = { action, version };
          if (category) payload.category = category;
          await this.requestJson(this.endpoint(id), {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
        }
        this.setStatus(action === "undo" ? "Решение отменено." : "Решение сохранено для пакета.");
        await this.loadNextUnresolved();
      } catch (error) {
        this.setBusy(article, false);
        this.setStatus(error.message, true);
      }
    }

    async saveMember(root, reviewId, version, action, category) {
      if (!reviewId) {
        this.setStatus("Не удалось определить строку проверки. Обновите страницу и повторите действие.", true);
        return;
      }
      this.setBusy(root, true);
      try {
        const payload = { action };
        if (typeof version === "string" && version) payload.version = version;
        if (category) payload.category = category;
        await this.requestJson(this.itemEndpoint(reviewId), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        this.setStatus(action === "exclude" ? "Строка исключена из пакета и требует отдельного решения." : "Решение для строки сохранено.");
        await this.loadNextUnresolved();
      } catch (error) {
        this.setBusy(root, false);
        this.setStatus(error.message, true);
      }
    }

    async loadNextUnresolved() {
      this.filters.onlyUnresolved = true;
      this.onlyUnresolvedFilter.checked = true;
      await this.load(1, true);
    }

    focusNextVisiblePacket() {
      const packet = this.items.querySelector('[data-unresolved="true"] .apply-cluster-action, [data-unresolved="true"] .member-override summary');
      if (packet) packet.focus({ preventScroll: true });
      else if (!this.empty.hidden) this.empty.focus?.({ preventScroll: true });
      else this.items.focus({ preventScroll: true });
    }

    setBusy(root, busy) {
      root.querySelectorAll("button, select").forEach((control) => {
        control.disabled = busy;
      });
    }

    async apply() {
      this.applyButton.disabled = true;
      try {
        const payload = await this.requestJson(`/api/drawing-card/jobs/${encodeURIComponent(this.jobId)}/review/apply`, { method: "POST" });
        await this.renderJob(payload, this.page);
      } catch (error) {
        this.setStatus(error.message, true);
      } finally {
        if (!this.applyButton.hidden) this.applyButton.disabled = false;
      }
    }

    showLegacy(payload) {
      this.legacy.hidden = false;
      this.items.hidden = true;
      this.filtersForm.hidden = true;
      this.pagination.hidden = true;
      this.mobileBar.hidden = true;
      this.applyButton.hidden = true;
      this.reviewDownload.hidden = typeof payload.review_url !== "string" || !payload.review_url;
      if (!this.reviewDownload.hidden) this.reviewDownload.href = payload.review_url;
      this.reviewForm.hidden = payload.can_upload_review !== true;
      this.hint.textContent = "Проверьте файл замечаний и загрузите исправленную версию.";
      this.setStatus("Проверка доступна файлом. Исправьте замечания и загрузите его обратно.");
    }

    async uploadLegacy(event) {
      event.preventDefault();
      if (!this.jobId || !this.reviewForm.reportValidity()) {
        this.setStatus("Сначала подготовьте отчёт, затем выберите исправленный файл проверки.", true);
        return;
      }
      this.submitReview.disabled = true;
      try {
        const payload = await this.requestJson(`/api/drawing-card/jobs/${encodeURIComponent(this.jobId)}/review`, { method: "POST", body: new FormData(this.reviewForm) });
        await this.renderJob(payload, this.page);
      } catch (error) {
        this.setStatus(error.message, true);
      } finally {
        this.submitReview.disabled = false;
      }
    }
  }

  window.DrawingCardReviewPanel = DrawingCardReviewPanel;
})();

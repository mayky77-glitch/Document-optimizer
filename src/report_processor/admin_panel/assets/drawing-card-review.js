(() => {
  "use strict";

  const PAGE_SIZE = 20;
  const CATEGORIES = [
    ["pile_foundation", "Устройство свайного основания"],
    ["concrete_works", "Бетонные работы"],
    ["metal_structures", "Монтаж металлоконструкций"],
    ["tsg_driving", "Погружение ТСГ"],
    ["tt_installation", "Монтаж ТТ"],
    ["tt_valves_installation", "Монтаж ЗРА ТТ"],
    ["power_cable", "Прокладка кабеля, провода (Силовые сети)"],
    ["low_current_cable", "Прокладка кабеля, провода (Слаботочные сети)"],
  ];

  const text = (value, fallback = "Не указано") =>
    typeof value === "string" && value.trim()
      ? value
      : typeof value === "number"
        ? String(value)
        : fallback;

  const decisionLabel = (value) => ({
    approved: "Одобрено",
    rejected: "Отклонено",
    cost_only: "Учтена только стоимость",
    change_category: "Категория изменена",
    pending: "Ожидает решения",
    unresolved: "Ожидает решения",
  }[value] || "Ожидает решения");

  const categoryLabel = (value, label) =>
    text(label, CATEGORIES.find(([id]) => id === value)?.[1] || "Не указана");

  const reasonLabel = (value) => ({
    formula_or_excel_error: "Формула или ошибка Excel",
    unit_mismatch: "Единицы измерения не совпадают",
    semantic_suggestion: "Семантическая подсказка требует проверки",
    multiple_categories: "Подходит несколько категорий",
    model_suggestion: "Подсказка модели требует проверки",
    manual_review: "Нужна ручная проверка",
  }[value] || text(value));

  const firstValue = (source, keys) => {
    if (!source || typeof source !== "object") return undefined;
    for (const key of keys) {
      if (source[key] !== null && source[key] !== undefined) return source[key];
    }
    return undefined;
  };

  class DrawingCardReviewPanel {
    constructor({ requestJson, setStatus, setProgress, renderResult, persistSession }) {
      this.requestJson = requestJson;
      this.setStatus = setStatus;
      this.setProgress = setProgress;
      this.renderResult = renderResult;
      this.persistSession = persistSession;
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
      this.jobId = null;
      this.page = 1;
      this.totalPages = 1;
      this.previous.addEventListener("click", () => this.load(this.page - 1, true));
      this.next.addEventListener("click", () => this.load(this.page + 1, true));
      this.applyButton.addEventListener("click", () => this.apply());
      this.reviewForm.addEventListener("submit", (event) => this.uploadLegacy(event));
    }

    async show(payload, jobId, page = 1) {
      this.jobId = jobId;
      this.page = page;
      this.panel.hidden = false;
      this.legacy.hidden = true;
      this.items.hidden = false;
      this.applyButton.hidden = false;
      this.setProgress("review");
      try {
        await this.load(page);
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

    async load(page = 1, moveFocus = false) {
      if (!this.jobId) return;
      const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      const payload = await this.requestJson(`${this.endpoint()}?${query}`, { method: "GET" });
      this.render(payload);
      if (moveFocus) this.items.focus({ preventScroll: true });
    }

    render(payload) {
      const clusters = Array.isArray(payload.clusters)
        ? payload.clusters
        : Array.isArray(payload.items)
          ? payload.items
          : [];
      this.items.replaceChildren(...clusters.map((cluster) => this.renderCluster(cluster)));
      this.empty.hidden = clusters.length !== 0;
      this.page = Number(payload.page) || this.page;
      const total = Number(payload.total_clusters) || clusters.length;
      this.totalPages = Math.max(1, Math.ceil(total / (Number(payload.page_size) || PAGE_SIZE)));
      this.pagination.hidden = this.totalPages <= 1;
      this.previous.disabled = this.page <= 1;
      this.next.disabled = this.page >= this.totalPages;
      this.pageStatus.textContent = `Страница ${this.page} из ${this.totalPages} · групп: ${total}`;
      this.renderSummary(payload);
      const unresolvedClusters = Number(payload.unresolved_clusters);
      const unresolvedRows = Number(payload.unresolved_rows);
      const pending = Number.isFinite(unresolvedClusters) ? unresolvedClusters : total;
      this.applyButton.disabled = pending > 0 || payload.can_apply === false;
      this.hint.textContent = this.applyButton.disabled
        ? `Осталось решить: групп — ${pending}, строк — ${Number.isFinite(unresolvedRows) ? unresolvedRows : "не указано"}.`
        : "Все группы обработаны. Примените решения, чтобы собрать карточку.";
      this.persistSession("review", this.page);
    }

    renderSummary(payload) {
      const pairs = [
        ["Необработанные группы", payload.unresolved_clusters],
        ["Строки в необработанных группах", payload.unresolved_rows],
        ["Всего групп", payload.total_clusters],
        ["Всего строк", payload.total_rows],
      ];
      this.summary.replaceChildren(...pairs
        .filter(([, value]) => Number.isFinite(Number(value)))
        .map(([label, value]) => {
          const item = document.createElement("span");
          item.textContent = `${label}: ${value}`;
          return item;
        }));
    }

    renderCluster(cluster) {
      const article = document.createElement("article");
      article.className = "review-item review-cluster";
      const id = text(cluster.cluster_id, "");
      const version = text(cluster.version, "");
      const members = Array.isArray(cluster.members) ? cluster.members : [];
      const count = Number(cluster.member_count) || members.length;
      const selected = text(cluster.selected_category, "");
      const proposed = text(cluster.proposed_category, "");
      const decision = text(cluster.decision, "unresolved");
      const resolved = ["approved", "rejected", "cost_only", "change_category"].includes(decision);
      article.dataset.clusterId = id;
      article.innerHTML = `
        <header class="review-item-head">
          <div>
            <p class="review-kicker">Группа строк · ${count}</p>
            <h3></h3>
          </div>
          <p class="decision-status"></p>
        </header>
        <dl class="review-context review-cluster-context">
          <div><dt>Ед. в источнике</dt><dd data-field="source-unit"></dd></div>
          <div><dt>Ед. в цели</dt><dd data-field="target-unit"></dd></div>
          <div><dt>Предложенная категория</dt><dd data-field="proposed"></dd></div>
          <div><dt>Уверенность</dt><dd data-field="confidence"></dd></div>
          <div><dt>Причина</dt><dd data-field="reason"></dd></div>
          <div><dt>Стоимость группы</dt><dd class="aggregate-cost" data-field="aggregate-cost"></dd></div>
        </dl>
        <p class="selected-category" hidden></p>
        <div class="item-actions" aria-label="Решение по группе строк"></div>
        <div class="review-decision" aria-label="Выберите решение для группы строк">
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
      article.querySelector("h3").textContent = text(cluster.work_name, "Наименование работы не указано");
      article.querySelector(".decision-status").textContent = decisionLabel(decision);
      article.querySelector('[data-field="source-unit"]').textContent = text(cluster.source_unit);
      article.querySelector('[data-field="target-unit"]').textContent = text(cluster.target_unit);
      article.querySelector('[data-field="proposed"]').textContent = categoryLabel(proposed, cluster.proposed_category_label);
      article.querySelector('[data-field="confidence"]').textContent = Number.isFinite(Number(cluster.confidence))
        ? `${Math.round(Number(cluster.confidence) * 100)}%`
        : "Не указана";
      article.querySelector('[data-field="reason"]').textContent = reasonLabel(cluster.reason);
      article.querySelector('[data-field="aggregate-cost"]').textContent = text(
        firstValue(cluster, ["aggregate_total_cost", "total_cost"]),
        "Не указана",
      );
      article.querySelector(".review-context").after(this.renderMembers(members, count));
      const selectedLabel = article.querySelector(".selected-category");
      if (selected) {
        selectedLabel.hidden = false;
        selectedLabel.textContent = `Принятая категория: ${categoryLabel(selected, cluster.selected_category_label)}`;
      }
      this.configureActions(article, { id, version, resolved, decision, proposed });
      return article;
    }

    renderMembers(members, count) {
      const details = document.createElement("details");
      details.className = "cluster-members";
      const summary = document.createElement("summary");
      summary.textContent = `Строк в группе: ${count}. Показать состав`;
      const explanation = document.createElement("p");
      explanation.textContent = `Решение ниже будет применено ко всем ${count} строкам этой группы.`;
      details.append(summary, explanation);

      if (!members.length) {
        const empty = document.createElement("p");
        empty.className = "cluster-members-empty";
        empty.textContent = "Состав группы не получен.";
        details.append(empty);
        return details;
      }

      const scroll = document.createElement("div");
      scroll.className = "cluster-members-table-wrap";
      scroll.tabIndex = 0;
      scroll.setAttribute("aria-label", "Таблица состава группы строк");
      const table = document.createElement("table");
      table.className = "cluster-members-table";
      const caption = document.createElement("caption");
      caption.textContent = "Состав группы строк";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      ["Наименование", "Ед.", "Количество", "Стоимость"].forEach((label) => {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = label;
        headRow.append(cell);
      });
      head.append(headRow);
      const body = document.createElement("tbody");
      members.forEach((member) => {
        const row = document.createElement("tr");
        const values = [
          text(firstValue(member, ["work_name", "name", "display_name"]), "Не указано"),
          text(firstValue(member, ["source_unit", "unit"]), "—"),
          text(firstValue(member, ["quantity", "remaining_quantity"]), "—"),
          text(firstValue(member, ["total_cost", "cost", "remaining_total_cost"]), "—"),
        ];
        values.forEach((value, index) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          if (index === 3) cell.className = "member-cost";
          row.append(cell);
        });
        body.append(row);
      });
      table.append(caption, head, body);
      scroll.append(table);
      details.append(scroll);
      return details;
    }

    configureActions(article, state) {
      const actions = article.querySelector(".item-actions");
      const decision = article.querySelector(".review-decision");
      const category = article.querySelector(".category-input");
      category.append(new Option("Выберите категорию", ""));
      CATEGORIES.forEach(([value, label]) => category.append(new Option(label, value)));
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
        this.setStatus("Не удалось определить группу проверки. Обновите страницу и повторите действие.", true);
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
        this.setStatus(action === "undo" ? "Решение отменено." : "Решение сохранено для всей группы.");
        await this.load(this.page);
      } catch (error) {
        this.setBusy(article, false);
        this.setStatus(error.message, true);
      }
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
        this.renderResult(payload);
        const status = text(payload.status, "").toLowerCase();
        if (payload.result_url || status === "ready") {
          this.applyButton.hidden = true;
          this.setStatus("Решения применены. Карточка готова.");
        } else if (status === "processing") {
          this.applyButton.hidden = true;
          this.setStatus("Решения применены. Карточка готовится — дождитесь обновления статуса.");
        } else if (status === "blocked" || status === "failed") {
          this.applyButton.hidden = true;
          this.setStatus(
            status === "blocked"
              ? "Карточка не сформирована: обработка заблокирована."
              : "Карточка не сформирована: обработка завершилась с ошибкой.",
            true,
          );
        } else {
          this.applyButton.disabled = false;
          this.setStatus("Решения приняты, но локальная панель не вернула понятный статус.", true);
        }
      } catch (error) {
        this.setStatus(error.message, true);
      } finally {
        if (!this.applyButton.hidden) this.applyButton.disabled = false;
      }
    }

    showLegacy(payload) {
      this.legacy.hidden = false;
      this.items.hidden = true;
      this.pagination.hidden = true;
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
        this.setStatus("Сначала подготовьте карточку, затем выберите исправленный файл проверки.", true);
        return;
      }
      this.submitReview.disabled = true;
      try {
        const payload = await this.requestJson(`/api/drawing-card/jobs/${encodeURIComponent(this.jobId)}/review`, { method: "POST", body: new FormData(this.reviewForm) });
        this.renderResult(payload);
        this.setStatus(payload.result_url ? "Проверка загружена. Карточка готова." : "Проверка загружена.");
      } catch (error) {
        this.setStatus(error.message, true);
      } finally {
        this.submitReview.disabled = false;
      }
    }
  }

  window.DrawingCardReviewPanel = DrawingCardReviewPanel;
})();

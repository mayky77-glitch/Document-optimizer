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
      const clusters = Array.isArray(payload.clusters) ? payload.clusters : [];
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
      const count = Number(cluster.member_count) || 0;
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
        </dl>
        <details class="cluster-members">
          <summary>Строк в группе: ${count}</summary>
          <p>Решение ниже будет применено ко всем ${count} строкам этой группы.</p>
        </details>
        <p class="selected-category" hidden></p>
        <div class="item-actions" aria-label="Решение по группе строк"></div>
        <form class="category-editor" hidden>
          <label>Категория<select class="category-input" required></select></label>
          <button type="submit">Применить категорию</button>
          <button type="button" data-cancel-category>Отмена</button>
        </form>`;
      article.querySelector("h3").textContent = text(cluster.work_name, "Наименование работы не указано");
      article.querySelector(".decision-status").textContent = decisionLabel(decision);
      article.querySelector('[data-field="source-unit"]').textContent = text(cluster.source_unit);
      article.querySelector('[data-field="target-unit"]').textContent = text(cluster.target_unit);
      article.querySelector('[data-field="proposed"]').textContent = categoryLabel(proposed, cluster.proposed_category_label);
      article.querySelector('[data-field="confidence"]').textContent = Number.isFinite(Number(cluster.confidence))
        ? `${Math.round(Number(cluster.confidence) * 100)}%`
        : "Не указана";
      article.querySelector('[data-field="reason"]').textContent = reasonLabel(cluster.reason);
      const selectedLabel = article.querySelector(".selected-category");
      if (selected) {
        selectedLabel.hidden = false;
        selectedLabel.textContent = `Принятая категория: ${categoryLabel(selected, cluster.selected_category_label)}`;
      }
      this.configureActions(article, { id, version, resolved, decision, proposed });
      return article;
    }

    configureActions(article, state) {
      const actions = article.querySelector(".item-actions");
      const editor = article.querySelector(".category-editor");
      const category = article.querySelector(".category-input");
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
      } else {
        addAction("Одобрить", "approve", "approve-action");
        addAction("Отклонить", "reject", "danger-action");
        addAction("Учитывать только стоимость", "cost_only");
        const change = document.createElement("button");
        change.type = "button";
        change.textContent = "Изменить категорию";
        change.addEventListener("click", () => {
          editor.hidden = false;
          category.focus();
        });
        actions.append(change);
      }
      article.querySelector("[data-cancel-category]").addEventListener("click", () => {
        editor.hidden = true;
      });
      editor.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!category.value) {
          category.focus();
          return;
        }
        this.save(article, state.id, state.version, "change_category", category.value);
      });
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
        this.setStatus(payload.result_url ? "Решения применены. Карточка готова." : "Решения применены. Дождитесь подготовки карточки.");
      } catch (error) {
        this.setStatus(error.message, true);
        this.applyButton.disabled = false;
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

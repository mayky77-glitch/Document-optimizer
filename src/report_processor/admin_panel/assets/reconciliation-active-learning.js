(() => {
  "use strict";

  const STATES = new Set(["loading", "empty", "ready", "saving", "saved", "stale", "unavailable"]);
  const ACTIONS = new Map([
    ["accept_pattern", "Принять шаблон"],
    ["case_only", "Оставить только для этого случая"],
    ["split", "Разделить"],
    ["reject", "Отклонить"],
  ]);
  const INTENT_VERSION = "ActiveLearningIntent-1.0";
  const QUEUE_ID = /^active-learning-queue-[0-9a-f]{64}$/;
  const ITEM_ID = /^active-learning-item-[0-9a-f]{64}$/;
  const SHA_REF = /^sha256:[0-9a-f]{64}$/;
  const asArray = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "") => {
    if (typeof value !== "string") return fallback;
    const normalized = value.trim();
    return normalized && normalized.length <= 200 ? normalized : fallback;
  };
  const opaqueRef = (value, pattern) => {
    if (typeof value !== "string") return "";
    const normalized = value.trim();
    return normalized && pattern.test(normalized) ? normalized : "";
  };
  const count = (value) => Number.isSafeInteger(value) && value >= 0
    ? value
    : 0;
  const isAscending = (values) => values.every((value, index) => index === 0 || values[index - 1] < value);
  const canonicalSplitRefs = (value) => {
    const groups = asArray(value);
    if (groups.length < 2 || groups.length > 64) return [];
    const normalized = groups.map((group) => {
      if (!Array.isArray(group) || !group.length || group.length > 512) return [];
      const refs = group.map((ref) => opaqueRef(ref, SHA_REF));
      return refs.every(Boolean) && isAscending(refs) ? refs : [];
    });
    if (normalized.some((group) => !group.length) || !isAscending(normalized.map((group) => group.join(":")))) return [];
    const members = normalized.flat();
    return members.length <= 512 && new Set(members).size === members.length ? normalized : [];
  };
  const plural = (value, one, few, many = few) => {
    const tail = Math.abs(value) % 100;
    const last = tail % 10;
    return tail > 10 && tail < 20 ? many : last === 1 ? one : last > 1 && last < 5 ? few : many;
  };

  class ReconciliationActiveLearning {
    constructor({ root, getJobId, renderPayload, submitShadowAction }) {
      this.root = root;
      this.getJobId = getJobId;
      this.renderPayload = renderPayload;
      this.submitShadowAction = submitShadowAction;
      this.focusItemId = "";
      this.savingItemId = "";
      this.localState = "";
    }

    static supports(payload) {
      return Object.prototype.hasOwnProperty.call(payload || {}, "active_learning_queue");
    }

    clear() {
      this.focusItemId = "";
      this.savingItemId = "";
      this.localState = "";
      this.root.replaceChildren();
      this.root.hidden = true;
    }

    queueFrom(payload) {
      const source = payload?.active_learning_queue;
      if (Array.isArray(source)) return {
        state: source.length ? "ready" : "empty", items: source, queueId: "", expectedQueueFingerprint: "",
      };
      if (!source || typeof source !== "object") return {
        state: "unavailable", items: [], queueId: "", expectedQueueFingerprint: "",
      };
      const state = STATES.has(source.state) ? source.state : "ready";
      return {
        state,
        items: asArray(source.items),
        queueId: opaqueRef(source.queue_id, QUEUE_ID),
        expectedQueueFingerprint: opaqueRef(source.expected_queue_fingerprint, SHA_REF),
      };
    }

    itemFrom(value) {
      if (!value || typeof value !== "object") return null;
      const itemId = opaqueRef(value.item_id, ITEM_ID);
      const expectedItemFingerprint = opaqueRef(value.expected_item_fingerprint, SHA_REF);
      const title = text(value.title);
      if (!itemId || !expectedItemFingerprint || !title) return null;
      return {
        itemId,
        expectedItemFingerprint,
        kind: value.kind === "package" ? "package" : "pattern",
        title,
        category: text(value.category_label, "Категория не определена"),
        mode: value.mode === "cost_only" ? "Только стоимость" : "Количество + стоимость",
        familyCount: count(value.family_count),
        groupCount: count(value.group_count),
        rowCount: count(value.row_count),
        reduction: count(value.action_reduction),
        reason: text(value.reason, "Требуется решение оператора."),
        slots: asArray(value.slots).slice(0, 8).map((entry) => text(entry)).filter(Boolean),
        differences: asArray(value.differences).slice(0, 8).map((entry) => text(entry)).filter(Boolean),
        exceptions: asArray(value.exceptions).slice(0, 8).map((entry) => text(entry)).filter(Boolean),
        splitMemberRefs: canonicalSplitRefs(value.split_member_refs),
        actions: asArray(value.actions).slice(0, 4).filter((action) => ACTIONS.has(action)),
      };
    }

    render(payload) {
      this.payload = payload;
      const queue = this.queueFrom(payload);
      this.queue = {
        state: this.localState || queue.state,
        items: queue.items.slice(0, 50).map((item) => this.itemFrom(item)).filter(Boolean),
        queueId: queue.queueId,
        expectedQueueFingerprint: queue.expectedQueueFingerprint,
      };
      if (this.queue.state === "ready" && !this.queue.items.length) this.queue.state = "empty";
      this.root.hidden = false;
      this.root.replaceChildren(this.buildPanel());
      this.restoreFocus();
    }

    buildPanel() {
      const panel = document.createElement("section");
      panel.className = "active-learning-review";
      panel.setAttribute("aria-labelledby", "active-learning-title");
      const heading = document.createElement("div");
      heading.className = "active-learning-heading";
      const title = document.createElement("h3");
      title.id = "active-learning-title";
      title.tabIndex = -1;
      title.textContent = "Вопросы для уточнения";
      const copy = document.createElement("p");
      copy.textContent = "Подтвердите шаблон или уточните только этот случай. Безопасные пакеты доступны ниже.";
      heading.append(title, copy);
      panel.append(heading, this.buildState());
      if (this.queue.state === "ready" || this.queue.state === "saving") {
        const list = document.createElement("div");
        list.className = "active-learning-list";
        list.setAttribute("aria-live", "polite");
        this.queue.items.forEach((item, index) => list.append(this.buildCard(item, index)));
        panel.append(list);
      }
      return panel;
    }

    buildState() {
      const state = document.createElement("p");
      state.className = `active-learning-state is-${this.queue.state}`;
      state.setAttribute("role", "status");
      state.setAttribute("aria-live", "polite");
      const messages = {
        loading: "Подбираем вопросы для уточнения. Безопасные пакеты уже можно проверить.",
        empty: "Новых вопросов нет. Продолжите проверку безопасных пакетов ниже.",
        ready: `Вопросов: ${this.queue.items.length}. Сначала показаны вопросы с наибольшим сокращением действий.`,
        saving: "Сохраняем решение. Другие вопросы остаются доступны.",
        saved: "Решение сохранено. Состав вопросов обновлён.",
        stale: "Данные изменились. Обновите сверку перед следующим решением.",
        unavailable: "Вопросы сейчас недоступны. Проверьте обычные пакеты ниже.",
      };
      state.textContent = messages[this.queue.state] || messages.unavailable;
      return state;
    }

    buildCard(item, index) {
      const card = document.createElement("article");
      card.className = "active-learning-card";
      card.tabIndex = 0;
      const focusKey = String(index);
      card.dataset.focusKey = focusKey;
      card.addEventListener("focus", () => { this.focusItemId = focusKey; });
      const head = document.createElement("header");
      const kind = document.createElement("p");
      kind.className = "active-learning-kicker";
      kind.textContent = item.kind === "package" ? "Пакет для уточнения" : "Шаблон для проверки";
      const title = document.createElement("h4");
      title.textContent = item.title;
      const proposal = document.createElement("p");
      proposal.className = "active-learning-proposal";
      proposal.textContent = `Предложено: ${item.category} · ${item.mode}`;
      head.append(kind, title, proposal);
      const impact = document.createElement("p");
      impact.className = "active-learning-impact";
      impact.textContent = `Сокращает до ${item.reduction} ${plural(item.reduction, "действия", "действий", "действий")}`;
      const coverage = document.createElement("p");
      coverage.className = "active-learning-coverage";
      coverage.textContent = `${item.familyCount} ${plural(item.familyCount, "семейство", "семейства", "семейств")} · ${item.groupCount} ${plural(item.groupCount, "группа", "группы", "групп")} · ${item.rowCount} ${plural(item.rowCount, "строка", "строки", "строк")}`;
      const reason = document.createElement("p");
      reason.className = "active-learning-reason";
      reason.textContent = item.reason;
      card.append(head, impact, coverage, reason, this.buildDetails(item), this.buildActions(item, focusKey));
      return card;
    }

    buildDetails(item) {
      const details = document.createElement("details");
      details.className = "active-learning-details";
      const summary = document.createElement("summary");
      summary.textContent = "Шаблон, различия и исключения";
      const body = document.createElement("div");
      body.className = "active-learning-detail-list";
      this.appendDetail(body, "Шаблон", item.slots);
      this.appendDetail(body, "Различия", item.differences);
      this.appendDetail(body, "Исключения", item.exceptions);
      details.append(summary, body);
      return details;
    }

    appendDetail(parent, label, entries) {
      if (!entries.length) return;
      const section = document.createElement("section");
      const heading = document.createElement("h5");
      heading.textContent = label;
      const list = document.createElement("ul");
      entries.forEach((entry) => {
        const row = document.createElement("li");
        row.textContent = entry;
        list.append(row);
      });
      section.append(heading, list);
      parent.append(section);
    }

    buildActions(item, focusKey) {
      const actions = document.createElement("div");
      actions.className = "active-learning-actions";
      if (this.queue.state === "stale" || this.queue.state === "unavailable") return actions;
      const offered = this.queue.queueId && this.queue.expectedQueueFingerprint
        ? item.actions.filter((action) => action !== "split" || item.splitMemberRefs.length > 1)
        : [];
      offered.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `active-learning-action is-${action}`;
        button.textContent = ACTIONS.get(action);
        button.disabled = this.savingItemId === item.itemId;
        button.addEventListener("click", () => { void this.save(item, action, focusKey); });
        actions.append(button);
      });
      if (!offered.length) {
        const hint = document.createElement("p");
        hint.className = "active-learning-action-hint";
        hint.textContent = "Действия для этого вопроса пока недоступны.";
        actions.append(hint);
      }
      return actions;
    }

    async save(item, action, focusKey) {
      if (this.savingItemId) return;
      const jobId = this.getJobId();
      if (!jobId || !this.queue.queueId || !this.queue.expectedQueueFingerprint) return;
      this.focusItemId = focusKey;
      this.savingItemId = item.itemId;
      this.localState = "saving";
      this.render(this.payload);
      try {
        this.localState = "";
        this.savingItemId = "";
        const decision = {
          queue_id: this.queue.queueId,
          expected_queue_fingerprint: this.queue.expectedQueueFingerprint,
          item_id: item.itemId,
          expected_item_fingerprint: item.expectedItemFingerprint,
          version: INTENT_VERSION,
          action,
          ...(action === "split" ? { split_member_refs: item.splitMemberRefs } : {}),
        };
        this.renderPayload(await this.submitShadowAction(jobId, item.itemId, decision));
      } catch (error) {
        this.savingItemId = "";
        this.localState = /stale|устар/i.test(text(error?.message)) ? "stale" : "unavailable";
        this.render(this.payload);
      }
    }

    restoreFocus() {
      if (!this.focusItemId || this.queue.state === "saved") return;
      const card = [...this.root.querySelectorAll(".active-learning-card")]
        .find((item) => item.dataset.focusKey === this.focusItemId);
      (card || this.root.querySelector("#active-learning-title"))?.focus({ preventScroll: true });
    }
  }

  window.ReconciliationActiveLearning = ReconciliationActiveLearning;
})();

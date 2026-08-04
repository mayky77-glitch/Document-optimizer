(() => {
  "use strict";

  const WEB_QUEUE_VERSION = "ActiveLearningWebQueue-1.0";
  const SHADOW_REQUEST_VERSION = "ActiveLearningShadowRequest-1.0";
  const MAX_INTEGER_AGGREGATE = 2147483647;
  const MAX_PRESENTATION_CODES = 32;
  const MAX_QUEUE_ITEMS = 512;
  const MAX_SPLIT_GROUPS = 64;
  const MAX_MEMBER_REFS = 512;
  const QUEUE_ID = /^active-learning-queue-[0-9a-f]{64}$/;
  const ITEM_ID = /^active-learning-item-[0-9a-f]{64}$/;
  const SHA_REF = /^sha256:[0-9a-f]{64}$/;
  const QUEUE_KEYS = [
    "version", "queue_id", "expected_queue_fingerprint", "expected_autosave_fingerprint", "items",
  ];
  const ITEM_KEYS = [
    "item_id", "expected_item_fingerprint", "kind", "mode", "coverage_family_count",
    "coverage_group_count", "affected_row_count", "affected_cost_minor_units",
    "document_frequency_count", "expected_action_reduction", "summary_codes", "difference_codes",
    "exception_codes", "allowed_actions", "split_member_refs",
  ];
  const KIND_LABELS = new Map([
    ["pattern", "Шаблон для проверки"],
    ["package", "Пакет для уточнения"],
  ]);
  const MODE_LABELS = new Map([
    ["quantity_cost", "Количество + стоимость"],
    ["cost_only", "Только стоимость"],
  ]);
  const ACTION_LABELS = new Map([
    ["accept_pattern", "Принять шаблон"],
    ["case_only", "Оставить только для этого случая"],
    ["split", "Разделить"],
    ["reject", "Отклонить"],
  ]);
  const CODE_LABELS = new Map([
    ["authority_unattested", "Нет подтверждённого основания"],
    ["cannot_link", "Нельзя объединять"],
    ["category_difference", "Различается категория"],
    ["critical_signature_difference", "Различается критический признак"],
    ["hard_negative", "Есть подтверждённое исключение"],
    ["mode_difference", "Различается способ учёта"],
    ["outlier", "Есть исключение"],
    ["package_candidate", "Кандидат в пакет"],
    ["pattern_candidate", "Кандидат в шаблон"],
    ["typed_signature_difference", "Различается типизированный признак"],
    ["unit_difference", "Различается единица"],
  ]);
  const ACTION_ORDER = [...ACTION_LABELS.keys()];
  const asArray = (value) => Array.isArray(value) ? value : [];
  const exactKeys = (value, keys) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const actual = Object.keys(value);
    return actual.length === keys.length && actual.every((key) => keys.includes(key));
  };
  const opaque = (value, pattern) => typeof value === "string" && pattern.test(value) ? value : "";
  const integer = (value) => Number.isSafeInteger(value) && value >= 0 && value <= MAX_INTEGER_AGGREGATE
    ? value
    : null;
  const ascending = (values) => values.every((value, index) => index === 0 || values[index - 1] < value);
  const codes = (value) => {
    if (!Array.isArray(value) || value.length > MAX_PRESENTATION_CODES) return null;
    return value.every((code) => CODE_LABELS.has(code))
      && new Set(value).size === value.length && ascending(value) ? value : null;
  };
  const actions = (value) => {
    if (!Array.isArray(value) || value.length > ACTION_ORDER.length) return null;
    const positions = value.map((action) => ACTION_ORDER.indexOf(action));
    return positions.every((position) => position >= 0)
      && new Set(value).size === value.length && ascending(positions) ? value : null;
  };
  const splitRefs = (value) => {
    if (!Array.isArray(value) || value.length > MAX_SPLIT_GROUPS) return null;
    if (!value.length) return [];
    if (value.length < 2) return null;
    const groups = value.map((group) => {
      if (!Array.isArray(group) || !group.length) return null;
      return group.every((ref) => opaque(ref, SHA_REF)) && ascending(group) ? group : null;
    });
    if (groups.some((group) => group === null)) return null;
    const members = groups.flat();
    return members.length <= MAX_MEMBER_REFS
      && new Set(members).size === members.length
      && ascending(groups.map((group) => group.join(":"))) ? groups : null;
  };
  const plural = (value, one, few, many = few) => {
    const tail = Math.abs(value) % 100;
    const last = tail % 10;
    return tail > 10 && tail < 20 ? many : last === 1 ? one : last > 1 && last < 5 ? few : many;
  };

  const parseItem = (value) => {
    if (!exactKeys(value, ITEM_KEYS)) return null;
    const itemId = opaque(value.item_id, ITEM_ID);
    const expectedItemFingerprint = opaque(value.expected_item_fingerprint, SHA_REF);
    const kind = KIND_LABELS.has(value.kind) ? value.kind : "";
    const mode = MODE_LABELS.has(value.mode) ? value.mode : "";
    const aggregates = [
      value.coverage_family_count, value.coverage_group_count, value.affected_row_count,
      value.affected_cost_minor_units, value.document_frequency_count, value.expected_action_reduction,
    ].map(integer);
    const summaryCodes = codes(value.summary_codes);
    const differenceCodes = codes(value.difference_codes);
    const exceptionCodes = codes(value.exception_codes);
    const allowedActions = actions(value.allowed_actions);
    const proposedSplit = splitRefs(value.split_member_refs);
    const requiredSummary = kind === "pattern" ? "pattern_candidate" : "package_candidate";
    if (!itemId || !expectedItemFingerprint || !kind || !mode || aggregates.some((item) => item === null)
      || !summaryCodes || !differenceCodes || !exceptionCodes || !allowedActions || proposedSplit === null
      || !summaryCodes.includes(requiredSummary)) return null;
    if ((allowedActions.includes("split")) !== Boolean(proposedSplit.length)) return null;
    if (kind === "package" && allowedActions.some((action) => action !== "split" && action !== "reject")) return null;
    return {
      itemId,
      expectedItemFingerprint,
      kind,
      mode,
      coverageFamilyCount: aggregates[0],
      coverageGroupCount: aggregates[1],
      affectedRowCount: aggregates[2],
      affectedCostMinorUnits: aggregates[3],
      documentFrequencyCount: aggregates[4],
      expectedActionReduction: aggregates[5],
      summaryCodes,
      differenceCodes,
      exceptionCodes,
      allowedActions,
      proposedSplit,
    };
  };

  const parseQueue = (value) => {
    if (!exactKeys(value, QUEUE_KEYS) || value.version !== WEB_QUEUE_VERSION
      || !Array.isArray(value.items) || value.items.length > MAX_QUEUE_ITEMS) return null;
    const queueId = opaque(value.queue_id, QUEUE_ID);
    const expectedQueueFingerprint = opaque(value.expected_queue_fingerprint, SHA_REF);
    const expectedAutosaveFingerprint = opaque(value.expected_autosave_fingerprint, SHA_REF);
    const items = value.items.map(parseItem);
    if (!queueId || !expectedQueueFingerprint || !expectedAutosaveFingerprint || items.some((item) => item === null)) return null;
    const records = items;
    return new Set(records.map((item) => item.itemId)).size === records.length
      ? { queueId, expectedQueueFingerprint, expectedAutosaveFingerprint, items: records }
      : null;
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
      this.cardsById = new Map();
      this.heading = null;
      this.queue = null;
    }

    static supports(payload) {
      return Object.prototype.hasOwnProperty.call(payload || {}, "active_learning_queue");
    }

    clear() {
      this.focusItemId = "";
      this.savingItemId = "";
      this.localState = "";
      this.cardsById = new Map();
      this.heading = null;
      this.queue = null;
      this.root.replaceChildren();
      this.root.hidden = true;
      return false;
    }

    render(payload) {
      this.payload = payload;
      const queue = parseQueue(payload?.active_learning_queue);
      this.queue = queue;
      this.cardsById = new Map();
      this.root.hidden = false;
      const state = this.localState || (queue ? (queue.items.length ? "ready" : "empty") : "unavailable");
      this.root.replaceChildren(this.buildPanel(state));
      return this.restoreFocus();
    }

    buildPanel(state) {
      const panel = document.createElement("section");
      panel.className = "active-learning-review";
      panel.setAttribute("aria-labelledby", "active-learning-title");
      const heading = document.createElement("h3");
      heading.id = "active-learning-title";
      heading.tabIndex = -1;
      heading.textContent = "Вопросы для уточнения";
      this.heading = heading;
      const status = document.createElement("p");
      status.className = `active-learning-state is-${state}`;
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      status.textContent = this.stateText(state);
      panel.append(heading, status);
      if ((state === "ready" || state === "saving") && this.queue) {
        const list = document.createElement("div");
        list.className = "active-learning-list";
        list.setAttribute("aria-live", "polite");
        this.queue.items.forEach((item) => list.append(this.buildCard(item, state)));
        panel.append(list);
      }
      return panel;
    }

    stateText(state) {
      const messages = {
        loading: "Подбираем вопросы для уточнения.",
        empty: "Новых вопросов нет.",
        ready: "Порядок вопросов определён на сервере.",
        saving: "Сохраняем решение.",
        saved: "Решение сохранено.",
        stale: "Данные изменились. Обновите сверку перед следующим решением.",
        unavailable: "Вопросы сейчас недоступны. Проверьте обычные пакеты ниже.",
      };
      return messages[state] || messages.unavailable;
    }

    buildCard(item, state) {
      const card = document.createElement("article");
      card.className = "active-learning-card";
      card.tabIndex = 0;
      card.addEventListener("focus", () => { this.focusItemId = item.itemId; });
      this.cardsById.set(item.itemId, card);
      const kind = document.createElement("p");
      kind.className = "active-learning-kicker";
      kind.textContent = KIND_LABELS.get(item.kind);
      const mode = document.createElement("p");
      mode.className = "active-learning-proposal";
      mode.textContent = MODE_LABELS.get(item.mode);
      const impact = document.createElement("p");
      impact.className = "active-learning-impact";
      impact.textContent = `Сокращение действий: ${item.expectedActionReduction}`;
      const coverage = document.createElement("p");
      coverage.className = "active-learning-coverage";
      coverage.textContent = `${item.coverageFamilyCount} ${plural(item.coverageFamilyCount, "семейство", "семейства", "семейств")} · ${item.coverageGroupCount} ${plural(item.coverageGroupCount, "группа", "группы", "групп")} · ${item.affectedRowCount} ${plural(item.affectedRowCount, "строка", "строки", "строк")}`;
      const aggregates = document.createElement("p");
      aggregates.className = "active-learning-reason";
      aggregates.textContent = `Затронутая стоимость, коп.: ${item.affectedCostMinorUnits} · Документов: ${item.documentFrequencyCount}`;
      card.append(kind, mode, impact, coverage, aggregates, this.buildDetails(item), this.buildActions(item, state));
      return card;
    }

    buildDetails(item) {
      const details = document.createElement("details");
      details.className = "active-learning-details";
      const summary = document.createElement("summary");
      summary.textContent = "Коды различий и исключений";
      const body = document.createElement("div");
      body.className = "active-learning-detail-list";
      this.appendCodes(body, "Основания", item.summaryCodes);
      this.appendCodes(body, "Различия", item.differenceCodes);
      this.appendCodes(body, "Исключения", item.exceptionCodes);
      details.append(summary, body);
      return details;
    }

    appendCodes(parent, label, values) {
      if (!values.length) return;
      const section = document.createElement("section");
      const heading = document.createElement("h4");
      heading.textContent = label;
      const list = document.createElement("ul");
      values.forEach((value) => {
        const row = document.createElement("li");
        row.textContent = CODE_LABELS.get(value);
        list.append(row);
      });
      section.append(heading, list);
      parent.append(section);
    }

    buildActions(item, state) {
      const actions = document.createElement("div");
      actions.className = "active-learning-actions";
      if (state !== "ready") return actions;
      if (!item.allowedActions.length) {
        const hint = document.createElement("p");
        hint.className = "active-learning-action-hint";
        hint.textContent = "Действия для этого вопроса недоступны.";
        actions.append(hint);
        return actions;
      }
      item.allowedActions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `active-learning-action is-${action}`;
        button.textContent = ACTION_LABELS.get(action);
        button.disabled = this.savingItemId === item.itemId;
        button.addEventListener("click", () => this.save(item, action));
        actions.append(button);
      });
      return actions;
    }

    async save(item, action) {
      if (!this.queue || this.savingItemId || !this.getJobId()) return false;
      this.focusItemId = item.itemId;
      this.savingItemId = item.itemId;
      this.localState = "saving";
      this.render(this.payload);
      const request = {
        version: SHADOW_REQUEST_VERSION,
        queue_id: this.queue.queueId,
        expected_queue_fingerprint: this.queue.expectedQueueFingerprint,
        expected_autosave_fingerprint: this.queue.expectedAutosaveFingerprint,
        item_id: item.itemId,
        expected_item_fingerprint: item.expectedItemFingerprint,
        action,
        split_member_refs: action === "split" ? item.proposedSplit : [],
      };
      try {
        this.localState = "";
        this.savingItemId = "";
        return this.renderPayload(await this.submitShadowAction(this.getJobId(), item.itemId, request)) === true;
      } catch (error) {
        this.savingItemId = "";
        this.localState = error?.code === "stale_state" ? "stale" : "unavailable";
        return this.render(this.payload);
      }
    }

    restoreFocus() {
      if (!this.focusItemId) return false;
      const card = this.cardsById.get(this.focusItemId);
      (card || this.heading)?.focus({ preventScroll: true });
      return Boolean(card || this.heading);
    }
  }

  window.ReconciliationActiveLearning = ReconciliationActiveLearning;
})();

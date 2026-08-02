(() => {
  "use strict";

  const PRIMARY_FILTERS = [
    { id: "safe", label: "Можно принять пакетом" },
    { id: "clarify", label: "Есть расхождения" },
    { id: "new", label: "Новые формулировки" },
    { id: "known", label: "Уже знакомые" },
    { id: "cost_only", label: "Только стоимость" },
    { id: "suspicious", label: "Подозрительные значения" },
  ];
  const queueOf = (item) => ["safe", "clarify", "new"].includes(item?.queue)
    ? item.queue
    : "";
  const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const value = (item, key) => typeof item?.[key] === "string" ? item[key] : "";
  const boolean = (item, key) => typeof item?.[key] === "boolean" ? item[key] : null;
  const modeOf = (item) => value(item, "mode") === "cost_only" ? "cost_only" : "quantity_cost";
  const categoryOf = (item) => value(item, "selected_category_id") || value(item, "proposed_category_id");
  const unitFamilyOf = (item) => value(item, "unit_family") || value(item, "unit") || "";
  const isKnown = (item) => boolean(item, "is_familiar") ?? (item?.known === true || item?.is_known === true);
  const readyForMass = (item) => boolean(item, "ready_for_mass_accept") ?? item?.safe === true;
  const isSuspicious = (item) => item?.suspicious === true
    || item?.has_suspicious_values === true
    || number(item?.suspicious_value_count) > 0;
  const isManuallyChanged = (item) => boolean(item, "manually_changed") ?? (
    value(item, "action") === "change_category"
      || (Boolean(value(item, "selected_category_id")) && categoryOf(item) !== value(item, "proposed_category_id"))
  );
  const sizeOf = (item) => {
    const rows = number(item?.row_count);
    if (rows <= 3) return "small";
    if (rows <= 10) return "medium";
    return "large";
  };

  const defaults = () => ({
    primary: "safe",
    category: "",
    mode: "",
    unitFamily: "",
    size: "",
    exceptions: "",
    readyForMass: "",
    manuallyChanged: "",
  });

  const unique = (values) => [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right, "ru-RU"));

  const select = (label, current, options, onChange, className = "") => {
    const field = document.createElement("label");
    field.className = `batch-secondary-field ${className}`.trim();
    const title = document.createElement("span");
    title.textContent = label;
    const control = document.createElement("select");
    options.forEach(([optionValue, optionLabel]) => control.append(new Option(optionLabel, optionValue)));
    control.value = current;
    control.addEventListener("change", () => onChange(control.value));
    field.append(title, control);
    return field;
  };

  const modeButtons = (current, onChange) => {
    const fieldset = document.createElement("fieldset");
    fieldset.className = "batch-secondary-mode";
    const legend = document.createElement("legend");
    legend.textContent = "Учёт";
    const options = document.createElement("div");
    [["", "Все"], ["quantity_cost", "Кол. + стоимость"], ["cost_only", "Только стоимость"]].forEach(([optionValue, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.setAttribute("aria-pressed", String(current === optionValue));
      button.classList.toggle("is-selected", current === optionValue);
      button.addEventListener("click", () => onChange(optionValue));
      options.append(button);
    });
    fieldset.append(legend, options);
    return fieldset;
  };

  const build = ({ packages, categories, state, onChange }) => {
    const toolbar = document.createElement("div");
    toolbar.className = "batch-filter-controls";
    const primary = document.createElement("div");
    primary.className = "batch-primary-filters";
    primary.setAttribute("role", "group");
    primary.setAttribute("aria-label", "Основной фильтр пакетов");
    PRIMARY_FILTERS.forEach((filter) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "batch-filter";
      button.textContent = filter.label;
      button.setAttribute("aria-pressed", String(state.primary === filter.id));
      button.classList.toggle("is-selected", state.primary === filter.id);
      button.addEventListener("click", () => onChange({ primary: filter.id }));
      primary.append(button);
    });

    const details = document.createElement("details");
    details.className = "batch-secondary-filters";
    const summary = document.createElement("summary");
    summary.textContent = "Дополнительные фильтры";
    const fields = document.createElement("div");
    fields.className = "batch-secondary-fields";
    fields.append(
      select("Категория", state.category, [["", "Все категории"], ...categories.map((category) => [category.id, category.label])], (category) => onChange({ category })),
      modeButtons(state.mode, (mode) => onChange({ mode })),
      select("Семейство единиц", state.unitFamily, [["", "Все семейства"], ...unique(packages.map(unitFamilyOf)).map((entry) => [entry, entry])], (unitFamily) => onChange({ unitFamily })),
      select("Размер пакета", state.size, [["", "Любой"], ["small", "До 3 строк"], ["medium", "4–10 строк"], ["large", "11+ строк"]], (size) => onChange({ size })),
      select("Исключения", state.exceptions, [["", "Все"], ["yes", "Есть"], ["no", "Нет"]], (exceptions) => onChange({ exceptions })),
      select("Готов для пакета", state.readyForMass, [["", "Все"], ["yes", "Да"], ["no", "Нет"]], (readyForMass) => onChange({ readyForMass })),
      select("Изменён вручную", state.manuallyChanged, [["", "Все"], ["yes", "Да"], ["no", "Нет"]], (manuallyChanged) => onChange({ manuallyChanged })),
    );
    details.append(summary, fields);
    toolbar.append(primary, details);
    return toolbar;
  };

  const matchesPrimary = (item, primary) => ({
    safe: queueOf(item) === "safe",
    clarify: queueOf(item) === "clarify",
    new: queueOf(item) === "new",
    known: isKnown(item),
    cost_only: modeOf(item) === "cost_only",
    suspicious: isSuspicious(item),
  })[primary] === true;

  const matches = (item, state) => matchesPrimary(item, state.primary)
    && (!state.category || categoryOf(item) === state.category)
    && (!state.mode || modeOf(item) === state.mode)
    && (!state.unitFamily || unitFamilyOf(item) === state.unitFamily)
    && (!state.size || sizeOf(item) === state.size)
    && (!state.exceptions || (state.exceptions === "yes") === (number(item?.exception_count) > 0))
    && (!state.readyForMass || (state.readyForMass === "yes") === readyForMass(item))
    && (!state.manuallyChanged || (state.manuallyChanged === "yes") === isManuallyChanged(item));

  window.ReconciliationBatchFilters = {
    build, defaults, matches, primaryFilters: PRIMARY_FILTERS, queueOf, readyForMass,
  };
})();

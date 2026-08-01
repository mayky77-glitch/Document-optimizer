(() => {
  "use strict";

  const STORAGE_KEY = "report-processor.theme.v1";
  const LEGACY_DRAWING_CARD_KEY = "report-processor.drawing-card.theme.v1";
  const toggle = document.querySelector("#theme-toggle");

  const storedTheme = () => {
    try {
      const theme = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_DRAWING_CARD_KEY);
      return theme === "dark" || theme === "light" ? theme : "light";
    } catch {
      return "light";
    }
  };

  const applyTheme = (theme, persist = true) => {
    const isDark = theme === "dark";
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(isDark));
      toggle.textContent = isDark ? "Светлая тема" : "Тёмная тема";
      toggle.setAttribute("aria-label", isDark ? "Включить светлую тему" : "Включить тёмную тему");
    }
    if (!persist) return;
    try {
      localStorage.setItem(STORAGE_KEY, isDark ? "dark" : "light");
    } catch {
      // Browser storage is optional.
    }
  };

  applyTheme(storedTheme(), false);
  toggle?.addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
})();

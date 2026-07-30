(() => {
  "use strict";

  const form = document.querySelector("#job-form");
  const status = document.querySelector("#status");
  const reviewPanel = document.querySelector("#review-panel");
  const summary = document.querySelector("#summary");
  const discrepancies = document.querySelector("#discrepancies");
  const suggestions = document.querySelector("#suggestions");
  const template = document.querySelector("#suggestion-template");
  const download = document.querySelector("#download");
  const submit = form.querySelector('button[type="submit"]');

  let currentJobId = null;

  const setProgress = (step) => {
    const order = ["files", "run", "review", "result"];
    const current = order.indexOf(step);
    document.querySelectorAll("[data-progress]").forEach((item, index) => {
      item.classList.toggle("is-active", index === current);
      item.classList.toggle("is-complete", index < current);
    });
  };

  const requestJson = async (url, options = {}) => {
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error("Сервер вернул некорректный ответ.");
    }
    if (!response.ok) {
      throw new Error(payload.error || "Операция не выполнена.");
    }
    return payload;
  };

  const renderSummary = (values) => {
    summary.replaceChildren();
    Object.entries(values || {}).forEach(([key, value]) => {
      const item = document.createElement("span");
      item.textContent = `${key}: ${value}`;
      summary.append(item);
    });
  };

  const renderDiscrepancies = (items) => {
    discrepancies.replaceChildren();
    (items || []).forEach((item) => {
      const row = document.createElement("li");
      row.className = item.category || "manual_review";
      row.textContent = `${item.code || "REVIEW"} — ${item.message || "Требуется проверка"}`;
      discrepancies.append(row);
    });
  };

  const decide = async (suggestionId, decision, card) => {
    card.querySelectorAll("button").forEach((button) => {
      button.disabled = true;
    });
    try {
      const payload = await requestJson(
        `/api/jobs/${encodeURIComponent(currentJobId)}/decisions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ suggestion_id: suggestionId, decision }),
        },
      );
      card.dataset.resolved = decision;
      card.querySelector(".candidate-list").textContent =
        decision === "fit"
          ? "Записано: подходит. Авторитетное сопоставление не изменено."
          : "Записано: не подходит. Авторитетное сопоставление не изменено.";
      renderDownload(payload);
    } catch (error) {
      card.querySelectorAll("button").forEach((button) => {
        button.disabled = false;
      });
      status.textContent = error.message;
    }
  };

  const renderSuggestions = (items) => {
    suggestions.replaceChildren();
    (items || []).forEach((item) => {
      const fragment = template.content.cloneNode(true);
      const card = fragment.querySelector(".suggestion-card");
      card.querySelector(".target-label").textContent =
        item.target_label || "Целевой этап";
      const score = Number(item.score || 0).toFixed(3);
      card.querySelector(".candidate-list").textContent =
        `${item.candidate_label || "Предложенный этап"} · уверенность ${score}`;
      card.querySelectorAll("[data-decision]").forEach((button) => {
        button.addEventListener("click", () => {
          decide(item.suggestion_id, button.dataset.decision, card);
        });
      });
      suggestions.append(fragment);
    });
  };

  const renderDownload = (payload) => {
    if (payload.download_url) {
      download.href = payload.download_url;
      download.textContent = "Скачать результат";
      download.classList.remove("is-disabled");
      download.removeAttribute("aria-disabled");
      setProgress("result");
      return;
    }
    download.removeAttribute("href");
    download.textContent = "Завершите ручную проверку";
    download.classList.add("is-disabled");
    download.setAttribute("aria-disabled", "true");
  };

  const renderJob = (payload) => {
    currentJobId = payload.job_id;
    renderSummary(payload.summary);
    renderDiscrepancies(payload.discrepancies);
    renderSuggestions(payload.suggestions);
    renderDownload(payload);
    reviewPanel.hidden = false;
    setProgress(payload.download_url ? "result" : "review");
    const labels = {
      ready: "Проверка завершена. Результат готов.",
      review_required: "Нужны явные решения по рекомендациям.",
      review_recorded: "Решения записаны. Доступен журнал проверки.",
      blocked: "Запись заблокирована правилами качества.",
      failed: "Обработка завершилась контролируемой ошибкой.",
    };
    status.textContent = labels[payload.status] || `Статус: ${payload.status}`;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    status.textContent = "Проверяем книги…";
    reviewPanel.hidden = true;
    setProgress("run");
    try {
      const payload = await requestJson("/api/jobs", {
        method: "POST",
        body: new FormData(form),
      });
      renderJob(payload);
    } catch (error) {
      status.textContent = error.message;
      setProgress("files");
    } finally {
      submit.disabled = false;
    }
  });
})();

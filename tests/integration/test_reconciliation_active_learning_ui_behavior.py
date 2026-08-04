"""Executable fake-DOM behavior checks for the inert active-learning queue."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ASSET = (
    Path(__file__).parents[2]
    / "src"
    / "report_processor"
    / "admin_panel"
    / "assets"
    / "reconciliation-active-learning.js"
)

HARNESS = r"""
;(async () => {
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

class Element {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
    this.className = "";
  }
  append(...children) {
    children.filter(Boolean).forEach((child) => {
      child.parentNode = this;
      this.children.push(child);
    });
  }
  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }
  setAttribute() {}
  addEventListener(name, handler) { this.listeners.set(name, handler); }
  focus() {
    document.activeElement = this;
    this.listeners.get("focus")?.();
  }
}

const document = {
  activeElement: null,
  createElement: (tagName) => new Element(tagName),
};
const window = {};
const context = {
  window, document, Map, Set, Number, Object, Array, Boolean, Math, Error,
};
vm.runInNewContext(fs.readFileSync(process.env.ACTIVE_LEARNING_ASSET, "utf8"), context);
const Review = window.ReconciliationActiveLearning;
const renderedText = (element) => (
  `${element.textContent || ""}${element.children.map(renderedText).join("")}`
);
const ref = (value) => `sha256:${value.repeat(64)}`;
const itemId = (value) => `active-learning-item-${value.repeat(64)}`;
const queueId = `active-learning-queue-${"f".repeat(64)}`;
const split = [[ref("a")], [ref("b")]];
const item = (value, overrides = {}) => ({
  item_id: itemId(value),
  expected_item_fingerprint: ref(value),
  kind: "pattern",
  mode: "quantity_cost",
  coverage_family_count: 1,
  coverage_group_count: 2,
  affected_row_count: 3,
  affected_cost_minor_units: 4,
  document_frequency_count: 5,
  expected_action_reduction: 6,
  summary_codes: ["pattern_candidate"],
  difference_codes: ["category_difference"],
  exception_codes: [],
  allowed_actions: ["accept_pattern", "case_only", "split", "reject"],
  split_member_refs: split,
  ...overrides,
});
const payload = (items) => ({ active_learning_queue: {
  version: "ActiveLearningWebQueue-1.0",
  queue_id: queueId,
  expected_queue_fingerprint: ref("c"),
  expected_autosave_fingerprint: ref("d"),
  items,
} });
const root = new Element("div");
const findButton = (element, label) => {
  if (element.tagName === "button" && element.textContent === label) return element;
  for (const child of element.children) {
    const found = findButton(child, label);
    if (found) return found;
  }
  return null;
};
let submitted = [];
let review;
review = new Review({
  root,
  getJobId: () => "job",
  renderPayload: (next) => review.render(next),
  submitShadowAction: async (_jobId, _itemId, request) => {
    submitted.push(request);
    return payload([item("2"), item("1")]);
  },
});

assert.strictEqual(Review.supports({ review_packages: [] }), false);
assert.strictEqual(Review.supports({ active_learning_queue: null }), true);
assert.strictEqual(review.render({ active_learning_queue: null }), false);
assert.strictEqual(review.queue, null);
const queueWithFreeField = {
  ...payload([item("1")]).active_learning_queue,
  title: "forbidden",
};
assert.strictEqual(review.render({ active_learning_queue: queueWithFreeField }), false);
assert.strictEqual(review.queue, null);

const first = item("1");
const second = item("2");
for (const malformed of [
  { ...first, title: "private-injected-value" },
  { ...first, kind: "forged" },
  { ...first, affected_row_count: true },
  { ...first, expected_action_reduction: 2147483648 },
]) {
  assert.strictEqual(review.render(payload([malformed])), false);
  assert.strictEqual(review.queue, null);
  assert.strictEqual(renderedText(root).includes("private-injected-value"), false);
}
assert.strictEqual(review.render(payload([{ ...first, split_member_refs: [[ref("a")]] }])), false);
assert.strictEqual(review.queue, null);
assert.strictEqual(review.render(payload(Array.from({ length: 513 }, () => first))), false);
assert.strictEqual(review.queue, null);
assert.strictEqual(review.render(payload([second, first])), false);
assert.strictEqual(
  JSON.stringify([...review.cardsById.keys()]),
  JSON.stringify([second.item_id, first.item_id]),
);
assert.strictEqual(review.cardsById.get(first.item_id).dataset.itemId, undefined);
review.cardsById.get(first.item_id).focus();
assert.strictEqual(review.render(payload([first, second])), true);
assert.strictEqual(document.activeElement, review.cardsById.get(first.item_id));
assert.strictEqual(review.render(payload([second])), true);
assert.strictEqual(document.activeElement, review.heading);

review.render(payload([first]));
assert.strictEqual(renderedText(root).includes("Затронутая стоимость, мин. ед.: 4"), true);
const rejectButton = findButton(root, "Отклонить");
assert.ok(rejectButton);
await rejectButton.listeners.get("click")();
assert.strictEqual(JSON.stringify(Object.keys(submitted[0]).sort()), JSON.stringify([
  "action", "expected_autosave_fingerprint", "expected_item_fingerprint",
  "expected_queue_fingerprint", "item_id", "queue_id", "split_member_refs", "version",
 ]));
assert.strictEqual(submitted[0].version, "ActiveLearningShadowRequest-1.0");
assert.strictEqual(JSON.stringify(submitted[0].split_member_refs), "[]");

review.render(payload([first]));
const splitButton = findButton(root, "Разделить");
assert.ok(splitButton);
await splitButton.listeners.get("click")();
assert.strictEqual(JSON.stringify(submitted[1].split_member_refs), JSON.stringify(split));
assert.strictEqual(document.activeElement, review.cardsById.get(first.item_id));

review.render(payload([item("3", { allowed_actions: [], split_member_refs: [] })]));
assert.strictEqual(renderedText(root).includes("Действия для этого вопроса недоступны."), true);

review.submitShadowAction = async () => {
  throw Object.assign(new Error("stale"), { code: "stale_state" });
};
review.render(payload([first]));
await review.save(review.queue.items[0], "reject");
assert.strictEqual(review.localState, "stale");
assert.strictEqual(review.render(payload([first])), true);
assert.strictEqual(document.activeElement, review.heading);
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
"""


def test_active_learning_queue_behavior_uses_only_the_closed_web_dto() -> None:
    environment = {**os.environ, "ACTIVE_LEARNING_ASSET": str(ASSET)}
    result = subprocess.run(
        ["node", "--eval", HARNESS],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr or result.stdout

"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import TargetWorkCategory


@dataclass(frozen=True, slots=True)
class CategoryRule:
    category: TargetWorkCategory
    display_name: str
    expected_units: tuple[str, ...]
    include_all: tuple[tuple[str, ...], ...]
    include_any: tuple[str, ...]
    exclude_any: tuple[str, ...]
    cost_only_any: tuple[str, ...]
    quantity_only_any: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RulesConfig:
    version: str
    categories: tuple[CategoryRule, ...]
    source_priority: tuple[str, ...]
    allow_template_unit_hint: bool
    min_model_confidence: float
    top_k_examples: int
    cost_scale: int
    cost_currency: str


@dataclass(frozen=True, slots=True)
class ModelConfig:
    base_url: str
    model: str
    api_key_env: str | None
    timeout: float
    max_tokens: int
    temperature: float


def _tuple_groups(value: Any) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(str(token) for token in group) for group in value or [])


def load_rules(path: Path) -> RulesConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    categories: list[CategoryRule] = []
    for item in payload["categories"]:
        categories.append(
            CategoryRule(
                category=TargetWorkCategory(item["id"]),
                display_name=str(item["display_name"]),
                expected_units=tuple(item.get("expected_units", [])),
                include_all=_tuple_groups(item.get("include_all")),
                include_any=tuple(item.get("include_any", [])),
                exclude_any=tuple(item.get("exclude_any", [])),
                cost_only_any=tuple(item.get("cost_only_any", [])),
                quantity_only_any=tuple(item.get("quantity_only_any", [])),
            )
        )
    return RulesConfig(
        version=str(payload.get("version", "unknown")),
        categories=tuple(categories),
        source_priority=tuple(payload.get("source_priority", ["visr", "ks6a", "ks2", "svvr"])),
        allow_template_unit_hint=bool(payload.get("allow_template_unit_hint", True)),
        min_model_confidence=float(payload.get("min_model_confidence", 0.7)),
        top_k_examples=int(payload.get("top_k_examples", 5)),
        cost_scale=int(payload.get("cost_scale", 1)),
        cost_currency=str(payload.get("cost_currency", "RUB")),
    )


def load_model_config(path: Path) -> ModelConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ModelConfig(
        base_url=str(payload["base_url"]).rstrip("/"),
        model=str(payload["model"]),
        api_key_env=payload.get("api_key_env"),
        timeout=float(payload.get("timeout", 60)),
        max_tokens=int(payload.get("max_tokens", 500)),
        temperature=float(payload.get("temperature", 0)),
    )

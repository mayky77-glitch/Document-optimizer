"""Strict OpenAI-compatible client for optional small-model classification."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
from jsonschema import validate

from ..config import ModelConfig
from ..models import TargetWorkCategory
from .examples import RetrievedExample

MODEL_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "category",
        "quantity_decision",
        "cost_decision",
        "confidence",
        "evidence_ids",
        "reason",
        "requires_confirmation",
    ],
    "properties": {
        "category": {"enum": [item.value for item in TargetWorkCategory]},
        "quantity_decision": {"enum": ["include", "exclude", "review"]},
        "cost_decision": {"enum": ["include", "exclude", "review"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "reason": {"type": "string", "minLength": 1},
        "requires_confirmation": {"type": "boolean"},
    },
}


@dataclass(frozen=True, slots=True)
class ModelClassificationRequest:
    source_text: str
    normalized_text: str
    unit: str | None
    drawing_code: str | None
    source_type: str | None
    negative_rules: tuple[str, ...]
    retrieved_examples: tuple[RetrievedExample, ...]


@dataclass(frozen=True, slots=True)
class ModelClassificationDecision:
    category: TargetWorkCategory
    quantity_decision: str
    cost_decision: str
    confidence: float
    evidence_ids: tuple[str, ...]
    reason: str
    requires_confirmation: bool


class OpenAICompatibleTinyModel:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def classify(self, request: ModelClassificationRequest) -> ModelClassificationDecision:
        api_key = os.getenv(self.config.api_key_env, "") if self.config.api_key_env else ""
        evidence = [
            {
                "example_id": item.example.example_id,
                "source_text": item.example.source_text,
                "category": item.example.category.value if item.example.category else None,
                "quantity_decision": item.example.quantity_decision,
                "cost_decision": item.example.cost_decision,
                "score": item.score,
            }
            for item in request.retrieved_examples
        ]
        prompt = {
            "task": "Classify one construction work row into exactly one allowed category.",
            "rules": [
                "Use only supplied evidence IDs.",
                "Never calculate or alter quantity, cost, unit, or drawing code.",
                "Return JSON only and always require confirmation.",
            ],
            "allowed_categories": [item.value for item in TargetWorkCategory],
            "row": {
                "source_text": request.source_text,
                "normalized_text": request.normalized_text,
                "unit": request.unit,
                "drawing_code": request.drawing_code,
                "source_type": request.source_type,
            },
            "negative_rules": list(request.negative_rules),
            "confirmed_examples": evidence,
            "response_schema": MODEL_RESPONSE_SCHEMA,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [
                {"role": "system", "content": "Return one strict JSON object without markdown."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(
                f"{self.config.base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        validate(parsed, MODEL_RESPONSE_SCHEMA)
        evidence_ids = tuple(parsed["evidence_ids"])
        allowed_ids = {item.example.example_id for item in request.retrieved_examples}
        if not set(evidence_ids).issubset(allowed_ids):
            raise ValueError("Model cited evidence outside the retrieved confirmed examples")
        if not parsed["requires_confirmation"]:
            raise ValueError("Model is not allowed to self-confirm")
        return ModelClassificationDecision(
            category=TargetWorkCategory(parsed["category"]),
            quantity_decision=parsed["quantity_decision"],
            cost_decision=parsed["cost_decision"],
            confidence=float(parsed["confidence"]),
            evidence_ids=evidence_ids,
            reason=str(parsed["reason"]),
            requires_confirmation=True,
        )

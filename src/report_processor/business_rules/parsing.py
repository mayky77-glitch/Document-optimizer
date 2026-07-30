"""Bounded JSON/YAML parsing with no executable configuration features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node
from yaml.tokens import AliasToken, AnchorToken, TagToken

MAX_CONFIGURATION_BYTES = 1024 * 1024
MAX_CONFIGURATION_DEPTH = 32


class ConfigurationParseError(ValueError):
    pass


def load_configuration_payload(path: Path) -> object:
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ConfigurationParseError("Поддерживаются только JSON, YAML и YML")
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigurationParseError(f"Не удалось прочитать конфигурацию: {error}") from error
    if len(raw) > MAX_CONFIGURATION_BYTES:
        raise ConfigurationParseError("Конфигурация превышает лимит 1 MiB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigurationParseError("Конфигурация должна быть UTF-8") from error
    if suffix == ".json":
        return _load_json(text)
    return _load_yaml(text)


def _load_json(text: str) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ConfigurationParseError(f"Повторяющийся JSON-ключ: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            text,
            object_pairs_hook=no_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ConfigurationParseError(f"Недопустимая JSON-константа: {value}")
            ),
        )
    except json.JSONDecodeError as error:
        raise ConfigurationParseError(f"Некорректный JSON: {error.msg}") from error


def _load_yaml(text: str) -> object:
    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise ConfigurationParseError("YAML tags, anchors и aliases запрещены")
        document = yaml.compose(text)
        if document is not None:
            _reject_duplicate_yaml_keys(document)
        payload = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigurationParseError(f"Некорректный YAML: {error}") from error
    if payload is None:
        raise ConfigurationParseError("Конфигурация не должна быть пустой")
    return payload


def _reject_duplicate_yaml_keys(node: Node) -> None:
    if isinstance(node, MappingNode):
        keys: set[str] = set()
        for key, value in node.value:
            if not isinstance(key.value, str) or key.value in keys:
                raise ConfigurationParseError(f"Повторяющийся YAML-ключ: {key.value}")
            keys.add(key.value)
            _reject_duplicate_yaml_keys(value)
    else:
        for child in getattr(node, "value", ()):
            if isinstance(child, Node):
                _reject_duplicate_yaml_keys(child)


def check_depth(value: object, depth: int = 0) -> None:
    if depth > MAX_CONFIGURATION_DEPTH:
        raise ConfigurationParseError("Превышен лимит вложенности 32")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationParseError("Ключи конфигурации должны быть строками")
            check_depth(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            check_depth(item, depth + 1)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")

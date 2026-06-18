"""Node type configuration with localized display names."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from rhine_vault.i18n import DEFAULT_LOCALE, Locale, normalize_locale

CONFIG_PACKAGE = "rhine_vault.config"
NODE_TYPES_FILE = "node_types.json"


def list_node_types(locale: str | None = None) -> list[dict[str, object]]:
    selected = normalize_locale(locale)
    config = _load_node_type_config()
    raw_items = config.get("node_types")
    if not isinstance(raw_items, list):
        raise ValueError("node_types config must contain a node_types list")
    return [_node_type_to_dict(raw, selected) for raw in raw_items]


def node_type_config(locale: str | None = None) -> dict[str, object]:
    selected = normalize_locale(locale)
    config = _load_node_type_config()
    policy = config.get("extension_policy", {})
    return {
        "locale": selected,
        "default_locale": DEFAULT_LOCALE,
        "extension_policy": policy if isinstance(policy, dict) else {},
        "node_types": list_node_types(selected),
    }


def _load_node_type_config() -> dict[str, Any]:
    text = files(CONFIG_PACKAGE).joinpath(NODE_TYPES_FILE).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("node_types config must be a JSON object")
    return data


def _node_type_to_dict(raw: object, locale: Locale) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("node type entry must be an object")
    node_type_id = _required_str(raw, "id")
    display_names = _required_locale_map(raw, "display_name")
    descriptions = _required_locale_map(raw, "description")
    return {
        "id": node_type_id,
        "display_name": _localized(display_names, locale),
        "description": _localized(descriptions, locale),
        "display_names": display_names,
        "descriptions": descriptions,
    }


def _required_str(raw: dict[Any, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"node type entry requires non-empty {key}")
    return value


def _required_locale_map(raw: dict[Any, Any], key: str) -> dict[str, str]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"node type entry requires {key} locale map")
    result: dict[str, str] = {}
    for locale, text in value.items():
        if not isinstance(locale, str) or not isinstance(text, str):
            raise ValueError(f"node type {key} values must be strings")
        result[locale] = text
    if DEFAULT_LOCALE not in result:
        raise ValueError(f"node type {key} requires default locale")
    return result


def _localized(values: dict[str, str], locale: Locale) -> str:
    return values.get(locale) or values[DEFAULT_LOCALE]

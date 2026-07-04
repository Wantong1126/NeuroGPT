# SPDX-License-Identifier: MIT
"""Provider configuration helpers."""
from __future__ import annotations

from copy import deepcopy

from core.config_loader import load_yaml_config

DEFAULT_PROVIDER_CONFIG = {
    "symptom_extractor": {
        "provider": "heuristic",
        "base_url": "",
        "model": "",
    },
    "summary_generator": {"provider": "heuristic"},
    "elder_explanation_generator": {
        "provider": "heuristic",
        "base_url": "",
        "model": "",
    },
    "observation_extractor_llm": {
        "provider": "heuristic",
        "base_url": "",
        "model": "",
    },
}



def load_provider_config() -> dict:
    config = deepcopy(DEFAULT_PROVIDER_CONFIG)
    try:
        raw = load_yaml_config("configs/providers.yaml")
    except FileNotFoundError:
        return config

    if not isinstance(raw, dict):
        return config

    for module_name, defaults in DEFAULT_PROVIDER_CONFIG.items():
        module_cfg = raw.get(module_name, {})
        if isinstance(module_cfg, dict):
            merged = defaults.copy()
            merged.update(module_cfg)
            config[module_name] = merged
    return config



def get_provider(module_name: str) -> str:
    config = load_provider_config()
    return config.get(module_name, {}).get("provider", "heuristic")


def get_provider_settings(module_name: str) -> dict:
    config = load_provider_config()
    return config.get(module_name, {}).copy()


def get_provider_base_url(module_name: str) -> str:
    settings = get_provider_settings(module_name)
    return str(settings.get("base_url") or "")


def get_provider_model(module_name: str) -> str:
    settings = get_provider_settings(module_name)
    return str(settings.get("model") or "")

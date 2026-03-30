# SPDX-License-Identifier: MIT
"""Provider configuration helpers."""
from __future__ import annotations

from copy import deepcopy

from core.config_loader import load_yaml_config

DEFAULT_PROVIDER_CONFIG = {
    "symptom_extractor": {"provider": "heuristic"},
    "summary_generator": {"provider": "heuristic"},
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

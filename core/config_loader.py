# SPDX-License-Identifier: MIT
"""NeuroGPT v2 — Config Loader"""
from __future__ import annotations
import os
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"

def load_yaml_config(relative_path: str) -> dict:
    path = PROJECT_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}

def load_prompt_template(template_name: str) -> str:
    path = CONFIGS_DIR / "llm_prompts" / f"{template_name}.md"
    if not path.exists(): return ""
    with open(path, "r", encoding="utf-8") as fh: return fh.read()

def load_disclaimer(key: str = "general.short") -> str:
    config = load_yaml_config("disclaimers.yaml")
    parts = key.split(".")
    value = config.get("disclaimers", {})
    for part in parts:
        value = value.get(part, "")
    return value

def get_action_for_risk(action_tier: str) -> dict:
    actions = load_yaml_config("action_tiers.yaml")
    return actions.get(action_tier, {})

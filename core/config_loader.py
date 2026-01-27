from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping at top level: {path}")
    return data


def load_config() -> Dict[str, Any]:
    root_dir = Path(__file__).resolve().parent.parent
    configs_dir = root_dir / "configs"

    config = {}
    config.update(_load_yaml(configs_dir / "language.yaml"))
    config.update(_load_yaml(configs_dir / "modes_enabled.yaml"))
    config.update(_load_yaml(configs_dir / "disclaimers.yaml"))
    config.update(_load_yaml(configs_dir / "model.yaml"))

    return config

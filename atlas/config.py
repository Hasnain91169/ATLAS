from pathlib import Path
from typing import Any

import yaml

from atlas.models.core import AtlasConfig


def load_config(path: str | Path) -> AtlasConfig:
    config_path = Path(path)
    raw_text = config_path.read_text(encoding="utf-8")
    data: Any = yaml.safe_load(raw_text)
    if data is None:
        raise ValueError("config file is empty")
    if not isinstance(data, dict):
        raise ValueError("config file must contain a mapping at the root")
    return AtlasConfig.model_validate(data)

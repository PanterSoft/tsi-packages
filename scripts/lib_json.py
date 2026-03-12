"""Shared JSON read/write helpers for TSI scripts."""

import json
from pathlib import Path
from typing import Any, Union


def load_json(filepath: Union[str, Path]) -> Any:
    """Load and parse a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def save_json(filepath: Union[str, Path], data: Any) -> None:
    """Save data as formatted JSON."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

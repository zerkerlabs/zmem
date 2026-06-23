from __future__ import annotations

from pathlib import Path
from typing import Any

from zerker_memory.integrations.activegraph import ZMemActiveGraphPack


class ZMemPack(ZMemActiveGraphPack):
    """Entry point object for ActiveGraph's pack loader."""

    manifest_path = Path(__file__).resolve().parents[1] / "pack" / "pack.yaml"

    def manifest(self) -> dict[str, Any]:
        return {
            "name": "zmem",
            "version": "0.1.0",
            "description": "Cross-session memory and bench runner for ActiveGraph agents",
            "entry_point": "zerker_memory.integrations.activegraph",
            "behaviors": self.behaviors,
        }

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_cache_root = Path(tempfile.gettempdir()) / "nethack_arena_submission_cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "xdg"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_root / "numba"))

from adapter_pf_base import AutoAscendDriver  # noqa: E402


class Bot:
    """daglar e29eb82's base engine (vkurenkov jawfish s25 238c254 + daglar's additions), on its own."""

    def __init__(self) -> None:
        self._driver = AutoAscendDriver()

    def reset(self, initial_observation: Mapping[str, Any]) -> None:
        self._driver.reset(initial_observation)

    def act(self, observation: Mapping[str, Any]) -> int:
        return self._driver.act(observation)

    def close(self) -> None:
        self._driver.close()


def make_agent():
    return Bot()

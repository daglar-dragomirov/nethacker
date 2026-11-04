from __future__ import annotations

import importlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import nle.nethack as nh
from nethackers.contracts.bot import ArenaBot

_cache_root = Path(tempfile.gettempdir()) / "nethack_arena_submission_cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "xdg"))
os.environ.setdefault("NUMBA_CACHE_DIR", str(_cache_root / "numba"))

_ACTION_TO_INDEX = {int(action): index for index, action in enumerate(nh.ACTIONS)}
_ATTR = _ACTION_TO_INDEX[int(nh.Command.ATTRIBUTES)]
_ESC = _ACTION_TO_INDEX[int(nh.Command.ESC)]
_CHOICES = json.loads((Path(__file__).resolve().parent / "identity-choices.json").read_text())
_RACES = {"human": "hum", "elven": "elf", "dwarven": "dwa", "gnomish": "gno", "orcish": "orc"}
_ROLES = {
    "Archeologist": "arc", "Barbarian": "bar", "Caveman": "cav",
    "Cavewoman": "cav", "Healer": "hea", "Knight": "kni",
    "Monk": "mon", "Priest": "pri", "Priestess": "pri",
    "Ranger": "ran", "Rogue": "rog", "Samurai": "sam",
    "Tourist": "tou", "Valkyrie": "val", "Wizard": "wiz",
}
_ALIGNMENTS = {"lawful": "law", "neutral": "neu", "chaotic": "cha"}


def _identity(observation: Mapping[str, Any]) -> str | None:
    screen = " ".join(bytes(row).decode("ascii", "replace") for row in observation["tty_chars"])
    background = re.search(r"a level [0-9]+ (?:(female|male) )?([A-Za-z]+) ([A-Za-z]+)\.", screen)
    alignment = re.search(r"You are (lawful|neutral|chaotic), on a mission", screen)
    if not background or not alignment:
        return None
    gender, race_name, role_name = background.groups()
    gender = gender or {"Cavewoman": "female", "Caveman": "male", "Priestess": "female", "Priest": "male", "Valkyrie": "female"}.get(role_name)
    race = _RACES.get(race_name)
    role = _ROLES.get(role_name)
    align = _ALIGNMENTS.get(alignment.group(1))
    if not race or not role or not align or not gender:
        return None
    return f"{role}-{race}-{align}-{'fem' if gender == 'female' else 'mal'}"


class Bot:
    def __init__(self) -> None:
        self._phase = "attributes"
        self._driver = None

    def reset(self, initial_observation: Mapping[str, Any]) -> None:
        del initial_observation
        self.close()
        self._phase = "attributes"

    def act(self, observation: Mapping[str, Any]) -> int:
        if self._phase == "attributes":
            self._phase = "select"
            return _ATTR
        if self._phase == "select":
            identity = _identity(observation)
            alias = _CHOICES.get(identity, "base")
            module = importlib.import_module(
                "arena_adapter_" + alias if alias != "base" else "arena_adapter"
            )
            self._driver = module.AutoAscendDriver()
            self._phase = "start"
            return _ESC
        if self._phase == "start":
            self._driver.reset(observation)
            self._phase = "play"
        return self._driver.act(observation)

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None


def make_agent() -> ArenaBot:
    return Bot()

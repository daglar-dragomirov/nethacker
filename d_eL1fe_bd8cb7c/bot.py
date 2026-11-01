"""Role router: plays each game with the engine that measured best for its role.

Layout of a router tree:
    bot.py              this file
    router.json         {"default": "<engine>", "roles": {"Monk": "<engine>", ...}}
    engines/<engine>/   a complete bot tree (its own bot.py, arena_adapter.py, autoascend/ ...)

The arena runs every game in its own process, so only one engine is ever imported per process and
engines that all name their package `autoascend` do not collide. The role is read from the game's
welcome line in the first observation.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ROLES = ('Archeologist', 'Barbarian', 'Caveman', 'Cavewoman', 'Healer', 'Knight', 'Monk', 'Priest',
         'Priestess', 'Ranger', 'Rogue', 'Samurai', 'Tourist', 'Valkyrie', 'Wizard')
CANONICAL = {'Cavewoman': 'Caveman', 'Priestess': 'Priest'}


def _text(observation: Mapping[str, Any]) -> str:
    parts = []
    for key in ('message', 'tty_chars'):
        value = observation.get(key)
        if value is not None:
            try:
                parts.append(bytes(bytearray(int(c) for c in value.reshape(-1))).decode('latin1'))
            except Exception:
                pass
    return ' '.join(parts)


RACES = {'human': 'human', 'elven': 'elf', 'dwarven': 'dwarf', 'gnomish': 'gnome', 'orcish': 'orc'}


# Xp 1 rank titles (role.c): on a full or new moon the moon message can replace the welcome line, and
# the status line ("Agent the Rambler") is all that names the role
TITLES = {'Digger': 'Archeologist', 'Plunderer': 'Barbarian', 'Plunderess': 'Barbarian',
          'Troglodyte': 'Caveman', 'Rhizotomist': 'Healer', 'Gallant': 'Knight', 'Candidate': 'Monk',
          'Aspirant': 'Priest', 'Tenderfoot': 'Ranger', 'Footpad': 'Rogue', 'Hatamoto': 'Samurai',
          'Rambler': 'Tourist', 'Stripling': 'Valkyrie', 'Evoker': 'Wizard'}


def detect_role(observation: Mapping[str, Any]) -> str | None:
    text = _text(observation)
    found = re.search(r'\b(' + '|'.join(ROLES) + r')\b', text)
    if found:
        return CANONICAL.get(found.group(1), found.group(1))
    title = re.search(r'\bthe (' + '|'.join(TITLES) + r')\b', text)
    return TITLES[title.group(1)] if title else None


def detect_race(observation: Mapping[str, Any]) -> str | None:
    found = re.search(r'\b(' + '|'.join(RACES) + r')\b', _text(observation))
    return RACES[found.group(1)] if found else None


def _load_engine(name: str):
    engine_dir = ROOT / 'engines' / name
    # the sandbox chdirs into the submission root; engines read their own files relative to it
    os.chdir(engine_dir)
    sys.path.insert(0, str(engine_dir))
    spec = importlib.util.spec_from_file_location(f'engine_{name}_bot', engine_dir / 'bot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Bot:
    def __init__(self) -> None:
        self._config = json.loads((ROOT / 'router.json').read_text())
        self._inner = None

    def reset(self, initial_observation: Mapping[str, Any]) -> None:
        if self._inner is None:
            role = detect_role(initial_observation)
            race = detect_race(initial_observation)
            # "Healer/gnome" beats "Healer" beats the default
            roles = self._config['roles']
            name = roles.get(f'{role}/{race}', roles.get(role, self._config['default']))
            self._inner = _load_engine(name).make_agent()
        self._inner.reset(initial_observation)

    def act(self, observation: Mapping[str, Any]) -> int:
        return self._inner.act(observation)

    def close(self) -> None:
        if self._inner is not None:
            self._inner.close()


def make_agent() -> Bot:
    return Bot()

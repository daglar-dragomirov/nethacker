"""Role router over two complete, unmodified programs.

Each subdirectory is an exact registered program (its own bot.py, engines, licenses):
  a368/  github.com/daglar-dragomirov/nethacker@a368786dc2650f8cd878b1226ac5815e719f164d  (default)
  eab9/  github.com/daglar-dragomirov/nethacker@eab9a9c4f4e09bce096d5762e895fec51b63784d
EAB9_ROLES lists the roles that play eab9; every other role -- and any game whose role can't be read -- plays a368.
The roles were chosen on fresh held-out games only (daglar-heldout/v1, see CHANGES.md), never on the private tier.

An arena episode is one process, so exactly one program is imported per game: its directory goes to the front of
sys.path and its bot.py is loaded under a private module name, which keeps the two programs' same-named modules
(roles, adapter, nhbot, ...) apart.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
EAB9_ROLES: frozenset[str] = frozenset({"arc", "cav"})

_ROLE_WORDS = {
    "archeologist": "arc", "barbarian": "bar", "caveman": "cav", "cavewoman": "cav", "healer": "hea", "knight": "kni",
    "monk": "mon", "priest": "pri", "priestess": "pri", "ranger": "ran", "rogue": "rog", "samurai": "sam",
    "tourist": "tou", "valkyrie": "val", "wizard": "wiz",
}
# rank titles at experience levels 1-2 (role.c), shown on the first status line as "Agent the <title>"
_TITLES = {
    "digger": "arc", "plunderer": "bar", "plunderess": "bar", "troglodyte": "cav", "rhizotomist": "hea",
    "gallant": "kni", "candidate": "mon", "aspirant": "pri", "tenderfoot": "ran", "footpad": "rog",
    "hatamoto": "sam", "rambler": "tou", "stripling": "val", "evoker": "wiz",
}


def _text(rows) -> str:
    try:
        return bytes(rows).decode("latin-1")
    except Exception:  # noqa: BLE001
        return ""


def role_of(observation) -> str | None:
    message = _text(observation["message"]).lower() if "message" in observation else ""
    if "welcome to nethack" in message:
        words = message.replace(".", " ").split()
        for word in reversed(words):
            if word in _ROLE_WORDS:
                return _ROLE_WORDS[word]
    try:
        for row in observation["tty_chars"][-3:]:
            line = _text(row).lower()
            if " the " in line:
                title = line.split(" the ", 1)[1].split()[0] if line.split(" the ", 1)[1].split() else ""
                if title in _TITLES:
                    return _TITLES[title]
    except Exception:  # noqa: BLE001
        pass
    return None


def _load(name: str):
    root = _HERE / name
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location(f"_program_{name}_bot", root / "bot.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.make_agent()


class Bot:
    def __init__(self) -> None:
        self._agent = None

    def reset(self, initial_observation) -> None:
        role = None
        try:
            role = role_of(initial_observation)
        except Exception:  # noqa: BLE001
            pass
        if self._agent is None:
            self._agent = _load("eab9" if role in EAB9_ROLES else "a368")
        self._agent.reset(initial_observation)

    def act(self, observation) -> int:
        return self._agent.act(observation)

    def close(self) -> None:
        if self._agent is not None and hasattr(self._agent, "close"):
            self._agent.close()


def make_agent() -> Bot:
    return Bot()

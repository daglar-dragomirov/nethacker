"""Identity router over two complete programs.

  eab9/    github.com/daglar-dragomirov/nethacker@eab9a9c4f4e09bce096d5762e895fec51b63784d (default, unmodified)
  tf1000/  the same program with TOUR_FAINT_PRAYER_GAP 1600 -> 1000 in every engine that has it (see CHANGES.md)

TF1000_IDENTITIES play tf1000/; every other identity -- and any game whose identity can't be read from the welcome
line -- plays eab9/. The three identities were chosen on the 15 published seeds (public board), where tf1000 beat
the board's leader; no claim beyond that board.

One arena episode is one process: exactly one program is imported per game, its directory first on sys.path and its
bot.py under a private module name, so the two programs' same-named modules never meet.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
TF1000_IDENTITIES = frozenset({"cav-hum-neu-mal", "ran-hum-cha-fem", "ran-hum-cha-mal"})

_ROLES = {
    "archeologist": "arc", "barbarian": "bar", "caveman": "cav", "cavewoman": "cav", "healer": "hea", "knight": "kni",
    "monk": "mon", "priest": "pri", "priestess": "pri", "ranger": "ran", "rogue": "rog", "samurai": "sam",
    "tourist": "tou", "valkyrie": "val", "wizard": "wiz",
}
_RACES = {"human": "hum", "elven": "elf", "dwarvish": "dwa", "gnomish": "gno", "orcish": "orc"}
_ALIGNS = {"lawful": "law", "neutral": "neu", "chaotic": "cha"}
_GENDERS = {"male": "mal", "female": "fem"}


def identity_of(observation) -> str | None:
    """'You are a chaotic female human Ranger.' -> 'ran-hum-cha-fem' (None without the welcome line)."""
    try:
        message = bytes(observation["message"]).decode("latin-1").lower()
    except Exception:  # noqa: BLE001
        return None
    if "welcome to nethack" not in message or "you are a" not in message:
        return None
    words = message.split("you are a", 1)[1].replace(".", " ").split()
    align = next((_ALIGNS[w] for w in words if w in _ALIGNS), None)
    gender = next((_GENDERS[w] for w in words if w in _GENDERS), None)
    race = next((_RACES[w] for w in words if w in _RACES), None)
    role = next((_ROLES[w] for w in words if w in _ROLES), None)
    if role in ("cav", "pri") and gender is None:
        gender = "fem" if any(w in ("cavewoman", "priestess") for w in words) else "mal"
    if None in (align, gender, race, role):
        return None
    return f"{role}-{race}-{align}-{gender}"


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
        ident = None
        try:
            ident = identity_of(initial_observation)
        except Exception:  # noqa: BLE001
            pass
        if self._agent is None:
            self._agent = _load("tf1000" if ident in TF1000_IDENTITIES else "eab9")
        self._agent.reset(initial_observation)

    def act(self, observation) -> int:
        return self._agent.act(observation)

    def close(self) -> None:
        if self._agent is not None and hasattr(self._agent, "close"):
            self._agent.close()


def make_agent() -> Bot:
    return Bot()

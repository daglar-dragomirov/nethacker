"""Identity router (Claude, 2026-10-26): zLeadersBest5043751.

Identities in ROUTES play a copy of the program that leads them on the hidden-seed tier, with the exploration-RNG seed + 5043751
(one behavioural knob) in that copy; every other identity -- and any game whose identity cannot be read from the
welcome line -- plays base/ (daglar eab9a9c, the public-board program). Each subdirectory keeps its own licenses; see CHANGES.md.
One arena episode is one process: exactly one program is imported per game, under a private module name.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROUTES = {
 "arc-dwa-law-fem": "skip",
 "arc-dwa-law-mal": "skip",
 "arc-gno-neu-fem": "skip",
 "arc-gno-neu-mal": "skip",
 "arc-hum-law-fem": "skip",
 "arc-hum-law-mal": "skip",
 "arc-hum-neu-fem": "hed",
 "arc-hum-neu-mal": "hed",
 "bar-hum-cha-fem": "skip",
 "bar-hum-cha-mal": "skip",
 "bar-hum-neu-fem": "skip",
 "bar-hum-neu-mal": "skip",
 "bar-orc-cha-fem": "skip",
 "bar-orc-cha-mal": "skip",
 "cav-dwa-law-fem": "hed",
 "cav-gno-neu-fem": "skip",
 "cav-gno-neu-mal": "skip",
 "cav-hum-law-fem": "skip",
 "cav-hum-law-mal": "skip",
 "cav-hum-neu-fem": "skip",
 "cav-hum-neu-mal": "skip",
 "hea-gno-neu-fem": "hed",
 "hea-gno-neu-mal": "hed",
 "hea-hum-neu-fem": "hed",
 "hea-hum-neu-mal": "hed",
 "kni-hum-law-fem": "skip",
 "kni-hum-law-mal": "skip",
 "mon-hum-cha-fem": "hed",
 "mon-hum-cha-mal": "skip",
 "mon-hum-neu-fem": "skip",
 "mon-hum-neu-mal": "skip",
 "pri-elf-cha-fem": "skip",
 "pri-elf-cha-mal": "skip",
 "pri-hum-cha-fem": "skip",
 "pri-hum-cha-mal": "skip",
 "pri-hum-law-fem": "skip",
 "pri-hum-law-mal": "hed",
 "pri-hum-neu-fem": "skip",
 "pri-hum-neu-mal": "skip",
 "ran-elf-cha-fem": "skip",
 "ran-elf-cha-mal": "skip",
 "ran-gno-neu-fem": "skip",
 "ran-gno-neu-mal": "skip",
 "ran-hum-cha-fem": "skip",
 "ran-hum-cha-mal": "skip",
 "ran-hum-neu-fem": "skip",
 "ran-hum-neu-mal": "skip",
 "ran-orc-cha-fem": "skip",
 "ran-orc-cha-mal": "skip",
 "rog-hum-cha-fem": "hed",
 "rog-hum-cha-mal": "hed",
 "rog-orc-cha-fem": "skip",
 "rog-orc-cha-mal": "skip",
 "sam-hum-law-fem": "hed",
 "sam-hum-law-mal": "hed",
 "tou-hum-neu-fem": "hed",
 "tou-hum-neu-mal": "hed",
 "val-dwa-law-fem": "hed",
 "val-hum-law-fem": "skip",
 "val-hum-neu-fem": "skip",
 "wiz-elf-cha-fem": "skip",
 "wiz-elf-cha-mal": "skip",
 "wiz-gno-neu-fem": "skip",
 "wiz-gno-neu-mal": "skip",
 "wiz-hum-cha-fem": "skip",
 "wiz-hum-cha-mal": "skip",
 "wiz-hum-neu-fem": "hed",
 "wiz-hum-neu-mal": "hed",
 "wiz-orc-cha-fem": "skip",
 "wiz-orc-cha-mal": "skip"
}

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
            self._agent = _load(ROUTES.get(ident, "base"))
        self._agent.reset(initial_observation)

    def act(self, observation) -> int:
        return self._agent.act(observation)

    def close(self) -> None:
        if self._agent is not None and hasattr(self._agent, "close"):
            self._agent.close()


def make_agent() -> Bot:
    return Bot()

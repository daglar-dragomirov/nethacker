"""Identity router (Claude, 2026-10-26): zLeadersEDt31000.

Identities in ROUTES play a copy of the program that leads them on the hidden-seed tier, with DIVE_TURN 31000
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
 "arc-dwa-law-fem": "d_kefirski_91cc604",
 "arc-dwa-law-mal": "d_kefirski_91cc604",
 "arc-gno-neu-fem": "d_alexeyshmelev_1fc7508",
 "arc-gno-neu-mal": "d_alexeyshmelev_1fc7508",
 "arc-hum-law-mal": "d_DT6A_58f484c",
 "arc-hum-neu-fem": "d_DT6A_070aea3",
 "arc-hum-neu-mal": "d_DT6A_070aea3",
 "bar-hum-cha-mal": "d_CleverShovel_911c949",
 "bar-hum-neu-fem": "d_tabt_800e2ae",
 "bar-hum-neu-mal": "d_eL1fe_012dce4",
 "cav-dwa-law-fem": "d_zarutskiysy_71335bf",
 "cav-dwa-law-mal": "d_zarutskiysy_71335bf",
 "cav-hum-neu-fem": "d_CleverShovel_0e6841c",
 "cav-hum-neu-mal": "d_CleverShovel_0e6841c",
 "hea-gno-neu-fem": "d_zarutskiysy_bb7def3",
 "hea-gno-neu-mal": "d_zarutskiysy_9c1cc90",
 "hea-hum-neu-fem": "d_DT6A_751f31d",
 "hea-hum-neu-mal": "d_DT6A_3e64892",
 "mon-hum-cha-fem": "d_DT6A_448d8d6",
 "mon-hum-law-fem": "d_tabt_16a066e",
 "mon-hum-law-mal": "d_DT6A_e97fc7d",
 "mon-hum-neu-mal": "d_CleverShovel_9c7a0f5",
 "pri-hum-law-fem": "d_Luab_a783b6d",
 "pri-hum-law-mal": "d_Luab_a783b6d",
 "pri-hum-neu-mal": "d_DT6A_eeffe21",
 "ran-elf-cha-fem": "d_artfawl_9f41c5e",
 "ran-elf-cha-mal": "d_AlexWortega_cc24e8a",
 "rog-hum-cha-fem": "d_eL1fe_bd8cb7c",
 "rog-hum-cha-mal": "d_HalcyonForest_6fa1dfd",
 "sam-hum-law-fem": "d_CleverShovel_f1e9153",
 "tou-hum-neu-fem": "d_DT6A_7a341b7",
 "tou-hum-neu-mal": "d_DT6A_7a341b7",
 "val-dwa-law-fem": "d_HalcyonForest_6fa1dfd",
 "val-hum-neu-fem": "d_HalcyonForest_6fa1dfd",
 "wiz-hum-neu-fem": "d_CleverShovel_911c949",
 "wiz-hum-neu-mal": "d_CleverShovel_911c949"
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

"""Fast resign (Claude, 2026-11-17): this program does not compete on this identity.

The router sends every identity it does not target here. The agent ends the game quickly by ordinary game means: it
prays again and again (a prayer too soon angers the god; repeated anger ends in the god's lightning or a lost level at
XL 1). It answers yes/no prompts with 'y', dismisses --More-- and escapes any other prompt. No engine is loaded.
"""
from __future__ import annotations

import nle.nethack as nh

_ACTIONS = tuple(int(a) for a in nh.ACTIONS)
_IDX = {a: i for i, a in enumerate(_ACTIONS)}
_PRAY = _IDX[int(nh.Command.PRAY)]
_YES = _IDX[ord('y')]
_MORE = _IDX[int(nh.MiscAction.MORE)]
_ESC = _IDX[int(nh.Command.ESC)]


def _text(observation, key):
    value = observation.get(key) if hasattr(observation, 'get') else None
    if value is None:
        return ''
    try:
        return bytes(bytearray(int(c) & 0xFF for c in value.reshape(-1))).decode('latin-1')
    except Exception:  # noqa: BLE001
        return ''


class Bot:
    def __init__(self) -> None:
        self._last = None

    def reset(self, initial_observation) -> None:
        self._last = None

    def act(self, observation) -> int:
        screen = _text(observation, 'tty_chars')
        message = _text(observation, 'message').strip('\x00 ')
        if '--More--' in screen or '--More--' in message:
            return _MORE
        if '[yn' in message or '[ynq' in message or '? [y' in screen:
            return _YES
        if message.endswith('?') or 'What do you want' in message or 'In what direction' in message:
            return _ESC
        return _PRAY

    def close(self) -> None:
        pass


def make_agent() -> Bot:
    return Bot()

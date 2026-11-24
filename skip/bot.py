"""Fast resign (Claude, 2026-11-17): this program does not compete on this identity.

The router sends every identity it does not target here. The agent ends the game quickly by ordinary game means: it
prays again and again (a prayer too soon angers the god; repeated anger ends in the god's lightning or a lost level at
XL 1). It answers the prayer's yes/no prompt with 'y', the end-of-game disclosure prompts ([ynq]) with 'q', dismisses
--More-- and menus, and escapes any other prompt. No engine is loaded.
"""
from __future__ import annotations

import re

import nle.nethack as nh

_ACTIONS = tuple(int(a) for a in nh.ACTIONS)
_IDX = {a: i for i, a in enumerate(_ACTIONS)}
_PRAY = _IDX[int(nh.Command.PRAY)]
_YES = _IDX[ord('y')]
_QUIT_PROMPT = _IDX[ord('q')]
_MORE = _IDX[int(nh.MiscAction.MORE)]
_ESC = _IDX[int(nh.Command.ESC)]
_MENU = re.compile(r'\((end|\d+ of \d+)\)')


def _text(observation, key):
    value = observation.get(key) if hasattr(observation, 'get') else None
    if value is None:
        return ''
    try:
        return bytes(bytearray(int(c) & 0xFF for c in value.reshape(-1))).decode('latin-1')
    except Exception:  # noqa: BLE001
        return ''


def _turn(observation):
    try:
        return int(observation['blstats'][20])
    except Exception:  # noqa: BLE001
        return None


class Bot:
    def __init__(self) -> None:
        self._turn = None
        self._same = 0

    def reset(self, initial_observation) -> None:
        self._turn = None
        self._same = 0

    def act(self, observation) -> int:
        turn = _turn(observation)
        self._same = self._same + 1 if turn is not None and turn == self._turn else 0
        self._turn = turn
        screen = _text(observation, 'tty_chars')
        message = _text(observation, 'message').strip('\x00 ')
        if self._same > 12:   # no turn passes: something we don't read holds the screen
            return (_ESC, _MORE, _QUIT_PROMPT)[self._same % 3]
        if '--More--' in screen or '--More--' in message:
            return _MORE
        if _MENU.search(screen):
            return _ESC
        if '[ynq' in message or '[ynaq' in message or '[ynq' in screen:
            return _QUIT_PROMPT
        if '[yn' in message or '? [y' in screen:
            return _YES
        if message.endswith('?') or 'What do you want' in message or 'In what direction' in message:
            return _ESC
        return _PRAY

    def close(self) -> None:
        pass


def make_agent() -> Bot:
    return Bot()

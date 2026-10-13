"""Development component: observed intervals and a read-operation lifecycle.

Interval parsing/refinement is adapted from Luab/nethacker b16051f (MIT).
Study event semantics are from exact NLE1.3.0 spell.c and allmain.c.
No NLE state, private trace or hidden spell memory is read by this module.
"""
from dataclasses import dataclass, replace
import re

KEEN = 20000
REFRESH_AT = KEEN // 10
USEFUL = ('force bolt', 'healing', 'extra healing')
ROW = re.compile(r'^([a-zA-Z]) -\s+(.+?)\s+(\d+)\s+(\w+)\s+(\d+)%\s+'
                 r'(\(gone\)|\d+%(?:-\d+%)?)\s*$')


@dataclass(frozen=True)
class Knowledge:
    letter: str
    name: str
    level: int
    category: str
    failure: float
    retention: tuple
    observed_turn: int
    expires_by: int

    def remaining_upper(self, turn):
        return max(0, self.expires_by - max(self.observed_turn, int(turn)))


def parse_row(text, turn):
    match = ROW.fullmatch(text)
    if match is None:
        raise ValueError('Invalid spell row: ' + repr(text))
    letter, name, level, category, failure, memory = match.groups()
    if memory == '(gone)':
        retention = (0, 0)
    else:
        ends = tuple(int(x.rstrip('%')) for x in memory.split('-'))
        retention = (ends[0], ends[-1])
    if not 0 <= int(failure) <= 100 or not 0 <= retention[0] <= retention[1] <= 100:
        raise ValueError('Invalid spell bounds: ' + repr(text))
    # Initialspell starts at KEEN; learn() uses KEEN+1. The full display
    # distinguishes neither. Keep the extra turn in the upper bound.
    upper = KEEN + 1 if retention == (100, 100) else retention[1] * 200
    return Knowledge(letter, name, int(level), category, int(failure) / 100,
                     retention, int(turn), int(turn) + upper)


def refine(previous, observed):
    if previous is None or previous.name != observed.name or observed.observed_turn < previous.observed_turn:
        return observed
    if observed.retention == (0, 0):
        return observed
    lower = ((observed.retention[0] - 1) * 200 + 1
             if observed.retention != (100, 100) else KEEN)
    aged_upper = previous.remaining_upper(observed.observed_turn)
    if lower > aged_upper:
        # A higher lower bound is observed replenishment, not just elapsed time.
        return observed
    return replace(observed, expires_by=min(previous.expires_by, observed.expires_by))


@dataclass
class Study:
    name: str
    started_turn: int
    started: bool = False
    terminal: str = None
    completed_turn: int = None
    verified: bool = False

    def observe(self, message, turn):
        """Only messages from this READ's bounded history slice may be passed.

        A terminal interruption/refusal never becomes success on a later stale
        message. A fresh READ/resumption needs a new Study operation.
        """
        if self.terminal is not None:
            return
        if ('You begin to memorize the runes.' in message or
                'You continue your efforts to memorize the spell.' in message):
            self.started = True
        quoted = re.escape('"' + self.name + '"')
        unknown_named = re.escape('the "' + self.name + '" spell')
        target = '(?:' + quoted + '|' + unknown_named + ')'
        complete = (re.search(r'Your knowledge of ' + target + r' is (?:keener|restored)\.', message) or
                    re.search(r'You learn ' + target + r'\.', message) or
                    re.search(r'You add ' + target + r' to your repertoire\.', message))
        if complete:
            self.terminal = 'completed_unverified'
            self.completed_turn = int(turn)
        elif ('too faint to be read any more' in message or
              'too faint to read even once' in message or
              'This spellbook is all blank.' in message or
              'The spellbook crumbles to dust!' in message):
            self.terminal = 'unusable'
        elif re.search(r'You know ' + target + r' quite well already\.', message):
            self.terminal = 'already_known_no_refresh'
        elif 'difficult to comprehend' in message:
            self.terminal = 'refused'
        elif 'You stop studying.' in message or 'You can move again.' in message:
            self.terminal = 'interrupted'

    def input_returned(self):
        # NLE moveloop drives the occupation between input requests. No WAIT
        # budget: if ordinary input returned without completion, stop here.
        if self.terminal is None:
            self.terminal = 'interrupted' if self.started else 'not_started'

    @property
    def may_query_completion(self):
        return self.terminal == 'completed_unverified'

    def verify(self, knowledge):
        if (self.may_query_completion and knowledge is not None and
                knowledge.name == self.name and
                knowledge.observed_turn >= self.completed_turn and
                knowledge.retention[0] >= 76):
            self.verified = True
        return self.verified


def eligible(knowledge, name, turn):
    # A refused CAST is represented by catalog=None at the adapter layer;
    # absence is unknown, not a new spell. An actual empty menu can learn.
    return knowledge is None or (knowledge.name == name and knowledge.remaining_upper(turn) <= REFRESH_AT)

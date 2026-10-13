"""Draft observable spell policy. Not installed in any evaluated program.

Contract from NLE1.3.0 spell.c: a completed learn() refresh and observed
retention are evidence. Starting READ, elapsed time and Pw loss alone are not.
No private data, probabilistic unknown-book reads or quest eligibility.
"""
from dataclasses import dataclass
from enum import Enum

USEFUL = frozenset(('force bolt', 'healing', 'extra healing', 'protection', 'cure blindness'))


@dataclass(frozen=True)
class Spell:
    name: str
    letter: str
    retention_percent: int
    failure_probability: float
    menu_turn: int


@dataclass(frozen=True)
class Player:
    turn: int
    experience_level: int
    hp: int
    max_hp: int
    energy: int
    burden: int
    hungry: bool
    weak_or_worse: bool
    blind: bool
    confused: bool
    stunned: bool
    hallucinating: bool
    polymorphed: bool
    deadly_status: bool
    hostile_distance: int | None
    safe_prayer_due: bool


def usable(spell, player, *, cost, maximum_failure, reserve=0):
    """Menu observations must be current for new elective self-casts."""
    return bool(
        len(spell.letter) == 1 and spell.letter.isascii() and spell.letter.isalpha()
        and 0 < spell.retention_percent <= 100
        and 0 <= spell.failure_probability <= maximum_failure
        and spell.menu_turn == player.turn
        and player.energy >= cost + reserve and player.burden < 2
        and not player.weak_or_worse and not player.confused and not player.stunned
        and not player.hallucinating and not player.polymorphed
        and not player.deadly_status and not player.safe_prayer_due
    )


def utility_spell(spells, player, last_attempt):
    """New utilities only; inherited healing/escape priority stays with caller.

    Protection is a bounded attempt, never an assertion of active protection.
    Re-evaluate current visible threat after each action. These policy values
    are prospective draft choices, not fitted or frozen experiment parameters.
    """
    cure = spells.get('cure blindness')
    if player.blind and cure and player.turn - last_attempt.get(cure.name, -1000) >= 10:
        if usable(cure, player, cost=10, maximum_failure=.20, reserve=5):
            return cure.name
    protect = spells.get('protection')
    if (protect and not player.blind and player.hostile_distance is not None
            and player.hostile_distance <= 2 and player.hp * 2 >= player.max_hp
            and player.turn - last_attempt.get(protect.name, -1000) >= 30
            and usable(protect, player, cost=5, maximum_failure=.20, reserve=5)):
        return protect.name
    return None


@dataclass(frozen=True)
class Book:
    name: str
    level: int
    status: str
    unambiguous: bool
    carried: bool
    in_shop: bool
    dull: bool


def refresh_eligible(book, spell, player, *, intelligence, wearing_lenses,
                     sleep_resistant, last_attempt_turn):
    """Known books only; uncursed study needs deterministic read ability.

    Ordinary random-generation BUC priors and inventory stack counts are never
    substitutes for observed status or kind. Actual type changes require the
    caller to resolve the current inventory item again before READ.
    """
    ability = intelligence + 4 + player.experience_level // 2 - 2 * book.level + (2 if wearing_lenses else 0)
    return bool(
        book.name in USEFUL and book.name == spell.name
        and book.unambiguous and book.carried and not book.in_shop
        and book.status in ('blessed', 'uncursed')
        and (book.status == 'blessed' or ability >= 20)
        and (not book.dull or sleep_resistant)
        and 0 <= spell.retention_percent <= 10 and spell.menu_turn == player.turn
        and player.turn - last_attempt_turn >= 200
        and player.hostile_distance is None and player.hp * 10 >= player.max_hp * 9
        and not player.hungry and player.burden < 2
        and not any((player.blind, player.confused, player.stunned, player.hallucinating,
                     player.polymorphed, player.deadly_status, player.safe_prayer_due))
    )


class StudyResult(str, Enum):
    PENDING = 'pending'
    REFRESHED = 'observed_refreshed'
    EXHAUSTED = 'observed_exhausted'
    NOT_NEEDED = 'observed_not_needed'
    INTERRUPTED = 'interrupted_or_unknown'


@dataclass
class Study:
    name: str
    started_turn: int
    starting_retention: int
    result: StudyResult = StudyResult.PENDING
    completion_message_seen: bool = False

    def observe(self, message, *, turn, current_retention=None, menu_turn=None):
        if self.result != StudyResult.PENDING:
            return self.result
        if turn < self.started_turn:
            return self.result
        # Completion text is advisory until a later menu verifies memory.
        if f'Your knowledge of "{self.name}" is keener.' in message or \
                f'Your knowledge of "{self.name}" is restored.' in message or \
                f'Your knowledge of the "{self.name}" spell is keener.' in message or \
                f'Your knowledge of the "{self.name}" spell is restored.' in message:
            self.completion_message_seen = True
        if 'too faint to be read any more' in message or 'too faint to read even once' in message:
            self.result = StudyResult.EXHAUSTED
        elif 'quite well already' in message:
            self.result = StudyResult.NOT_NEEDED
        elif (self.completion_message_seen and menu_turn == turn
              and current_retention is not None and current_retention > self.starting_retention
              and current_retention >= 90):
            self.result = StudyResult.REFRESHED
        return self.result

    def interrupted(self):
        if self.result == StudyResult.PENDING:
            self.result = StudyResult.INTERRUPTED
        return self.result

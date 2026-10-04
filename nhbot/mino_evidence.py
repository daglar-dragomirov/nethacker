"""Unintegrated sleep-evidence state machine for the next whole controller.

Inputs must come from actual game observations. This prototype does not access
engine internals and does not claim that a hit proves immobility. It distinguishes
recent attributed evidence from a possible sleeper and an unassociated threat.
"""
import re

HIT = re.compile(r'The sleep ray hits (?:the )?minotaur\b')
ACTS = re.compile(r'The minotaur (?:hits|misses|just misses|butts|bites)\b')
OUR_ATTACK = re.compile(r'You (?:hit|miss|smite|kick|bite|claw|punch|butt) (?:the )?minotaur\b')

class SleepEvidence:
    def __init__(self):
        self.level = None
        self.visible = set()
        self.entries = {}
        self.pending = None
        self.last_stamp = None
        self.last_turn = None
        self.last_message_stamp = -1

    def arm(self, *, level, turn, origin, target, visible):
        """One guard shot. The caller must disarm in finally after the action."""
        coords = set(visible)
        dy, dx = target[0] - origin[0], target[1] - origin[1]
        aligned = (dy != 0 or dx != 0) and (dy == 0 or dx == 0 or abs(dy) == abs(dx))
        self.pending = dict(level=level, turn=turn, origin=origin, target=target,
            visible=coords, aligned=aligned,
            was_possible=self.classify(target, level=level, turn=turn) != 'unassociated')

    def disarm(self):
        self.pending = None

    def invalidate_own_attack(self):
        """Any own attack may wake a sleeper; generic observations lack IDs."""
        self.entries.clear()

    def observe(self, *, level, turn, stamp, visible, message='', lost_hp=False, reliable=True,
                message_stamp=None):
        if self.last_stamp == (level, stamp):
            return
        self.last_stamp = (level, stamp)
        coords = set(visible)
        if level != self.level or not reliable or (self.last_turn is not None and
                (turn < self.last_turn or turn - self.last_turn > 1)):
            self.entries.clear()
        self.level = level
        self.last_turn = turn
        # A tile is not a monster identity. No revival after a visibility gap,
        # movement, a new level, expiry, hallucination or unreliable map state.
        self.entries = {coord: entry for coord, entry in self.entries.items()
            if reliable and coord in coords and coord in self.visible
            and 0 <= turn - entry['turn'] < 127}
        self.visible = coords
        # The Agent must restore this original message stamp alongside message
        # text after nested inventory/monster inspection. A genuinely new equal
        # attack string has a larger stamp and still invalidates evidence.
        event_stamp = stamp if message_stamp is None else message_stamp
        new_message = event_stamp > self.last_message_stamp
        self.last_message_stamp = max(event_stamp, self.last_message_stamp)
        acts = list(ACTS.finditer(message)) if new_message else []
        hits = list(HIT.finditer(message)) if new_message else []
        own_attack = bool(OUR_ATTACK.search(message)) if new_message else False
        if acts or own_attack or lost_hp:
            self.entries.clear()
        shot = self.pending
        if not hits or shot is None:
            return
        # Consume once even if attribution fails; an accumulated message or
        # subsequent inventory query cannot create or renew a sleep lease.
        self.pending = None
        if (not reliable or lost_hp or own_attack or shot['level'] != level or not shot['aligned']
                or not 0 <= turn - shot['turn'] <= 1 or shot['was_possible']
                or len(shot['visible']) != 1 or coords != shot['visible']
                or shot['target'] not in coords
                or 'reflects' in message.lower() or 'resists' in message.lower()
                or (acts and acts[-1].start() > hits[-1].start())):
            return
        self.entries[shot['target']] = dict(turn=shot['turn'],
            observed_turn=turn, evidence='attributed_sleep_hit', certainty='conditional')

    def classify(self, coord, *, level, turn):
        """Evidence strength, not the engine's asleep/mcanmove flag."""
        entry = self.entries.get(coord) if level == self.level else None
        if entry is None or not 0 <= turn - entry['turn'] < 127:
            return 'unassociated'
        # Five is a conservative model bound allowing one timeout boundary;
        # exact arena ordering must be checked before a gameplay integration.
        return 'recent_hit' if turn - entry['turn'] < 5 else 'possible_sleep'

"""Unintegrated conditional hit-attribution prototype for Wizard combat.

No hit proves that a creature is asleep. These classifications must never remove
a visible hostile from the risk model or override intact minotaur escape policy.
The caller supplies all visible coordinates of this name and stable observation
and message stamps, including those preserved after nested inventory inspection.
"""
import re

class CombatHitEvidence:

    def __init__(self, target_name):
        self.target_name = target_name
        assert isinstance(target_name, str) and target_name
        escaped = re.escape(target_name)
        self.hit_pattern = re.compile('The sleep ray hits (?:the )?' + escaped + '\\b')
        self.acts_pattern = re.compile('The ' + escaped + ' (?:hits|misses|just misses|butts|bites|kicks|claws|stings|touches|swings|thrusts)\\b')
        self.own_attack_pattern = re.compile('You (?:hit|miss|smite|kick|bite|claw|punch|butt)\\b')
        self.level = None
        self.visible = set()
        self.entries = {}
        self.pending = None
        self.last_stamp = None
        self.last_turn = None
        self.last_message_stamp = -1

    def arm(self, *, level, turn, origin, target, visible):
        """One shot at the unique visible creature of target_name. Disarm in finally."""
        coords = set(visible)
        dy, dx = (target[0] - origin[0], target[1] - origin[1])
        aligned = (dy != 0 or dx != 0) and (dy == 0 or dx == 0 or abs(dy) == abs(dx))
        self.pending = dict(level=level, turn=turn, origin=origin, target=target, visible=coords, aligned=aligned, was_possible=self.classify(target, level=level, turn=turn) != 'unassociated')

    def disarm(self):
        self.pending = None

    def invalidate_own_attack(self):
        """Any own attack may wake a sleeper; generic observations lack IDs."""
        self.entries.clear()

    def observe(self, *, level, turn, stamp, visible, message='', lost_hp=False, reliable=True, message_stamp=None):
        if self.last_stamp == (level, stamp):
            return
        self.last_stamp = (level, stamp)
        coords = set(visible)
        if level != self.level or not reliable or (self.last_turn is not None and (turn < self.last_turn or turn - self.last_turn > 1)):
            self.entries.clear()
        self.level = level
        self.last_turn = turn
        self.entries = {coord: entry for coord, entry in self.entries.items() if reliable and coord in coords and (coord in self.visible) and (0 <= turn - entry['turn'] < 127)}
        self.visible = coords
        event_stamp = stamp if message_stamp is None else message_stamp
        new_message = event_stamp > self.last_message_stamp
        self.last_message_stamp = max(event_stamp, self.last_message_stamp)
        acts = list(self.acts_pattern.finditer(message)) if new_message else []
        hits = list(self.hit_pattern.finditer(message)) if new_message else []
        own_attack = bool(self.own_attack_pattern.search(message)) if new_message else False
        if acts or own_attack or lost_hp:
            self.entries.clear()
        shot = self.pending
        if len(hits) != 1 or shot is None:
            return
        self.pending = None
        if not reliable or lost_hp or own_attack or (shot['level'] != level) or (not shot['aligned']) or (not 0 <= turn - shot['turn'] <= 1) or shot['was_possible'] or (len(shot['visible']) != 1) or (coords != shot['visible']) or (shot['target'] not in coords) or ('reflects' in message.lower()) or ('resists' in message.lower()) or (acts and acts[-1].start() > hits[-1].start()):
            return
        self.entries[shot['target']] = dict(turn=shot['turn'], observed_turn=turn, evidence='attributed_hit', certainty='conditional')

    def classify(self, coord, *, level, turn):
        """Evidence strength, not the engine's asleep/mcanmove flag."""
        entry = self.entries.get(coord) if level == self.level else None
        if entry is None or not 0 <= turn - entry['turn'] < 127:
            return 'unassociated'
        return 'recent_attributed_hit' if turn - entry['turn'] < 5 else 'aged_attributed_hit'

"""Adapted from HalcyonForest/nethacker@6fa1dfd2afb35b6fa6299c5e5d7cc4d0c7d731f6.

Offer plain food to a hunger-confused starting cat or dog.

Inspired by the parent's kni_steed.SteedKeeper. NetHack 3.6.6 dog.c accepts
plain food from a starving pet, and dothrow.c lets it land on the pet's square
even while confusion prevents an immediate catch.
"""

import re

import nle.nethack as nh

from . import utils
from .glyph import G, MON, Hunger
from .strategy import Strategy


PETS = frozenset(("kitten", "housecat", "large cat", "little dog", "dog", "large dog"))
PLAIN_FOOD = frozenset((
    "food ration", "cram ration", "lembas wafer", "tripe ration", "pancake",
    "candy bar", "apple", "carrot", "orange", "pear", "banana", "melon",
    "slime mold", "lump of royal jelly", "fortune cookie", "eucalyptus leaf",
))
# mhitu.c hitmsg names the hero hit with an exclamation; mhitm uses a target.
PET_ATTACK = re.compile(r"\b(?:The|Your) (kitten|housecat|large cat|little dog|dog|large dog) "
                        r"(?:bites|hits|kicks|butts)!", re.IGNORECASE)


class HungryPetFeeder:
    def __init__(self, agent):
        self.agent = agent
        self.last_throw = -1000

    def _food(self):
        foods = [item for item in self.agent.inventory.items
                 if item.category == nh.FOOD_CLASS and len(item.objs) == 1 and
                 item.objs[0].name in PLAIN_FOOD and
                 getattr(item, "shop_status", 0) != 2]
        # Retain at least one plain food unit for the hero; no new nutrition cutoff.
        if sum(item.count for item in foods) <= 1:
            return None
        return min(foods, key=lambda item: item.objs[0].nutrition)

    def _line_to(self, py, px):
        agent = self.agent
        y0, x0 = int(agent.blstats.y), int(agent.blstats.x)
        dy, dx = int(py) - y0, int(px) - x0
        distance = max(abs(dy), abs(dx))
        if distance < 1 or distance > 3 or not (dy == 0 or dx == 0 or abs(dy) == abs(dx)):
            return None
        sy, sx = int(dy > 0) - int(dy < 0), int(dx > 0) - int(dx < 0)
        level = agent.current_level()
        for k in range(1, distance):
            y, x = y0 + k * sy, x0 + k * sx
            glyph = agent.glyphs[y, x]
            if not level.walkable[y, x] or glyph in G.MONS or glyph in G.PETS or \
                    glyph in G.INVISIBLE_MON or glyph in G.BOULDER or \
                    level.objects[y, x] in G.DOOR_CLOSED:
                return None
        return sy, sx

    def _plan(self):
        agent = self.agent
        bl = agent.blstats
        # Cats/dogs use the same dogfood rules in all main-engine roles.
        if bl.hunger_state >= Hunger.WEAK or agent.character.prop.polymorph or \
                bl.time > agent._pet_starving_until or bl.time - self.last_throw < 5 or \
                agent.character.prop.hallu or agent.character.prop.blind or \
                agent.character.prop.confusion or agent.character.prop.stun:
            return None
        # A hunger message alone is not enough reason to spend the hero's last
        # ration. Feed only once the hungry pet has actually attacked us.
        attack = PET_ATTACK.search(agent.message or "")
        if attack is None:
            return None
        # Preserve the existing Knight keeper's radius; combat/escape takes priority.
        tracker = agent.monster_tracker
        hostile = tracker.monster_mask & ~tracker.peaceful_monster_mask
        for y, x in zip(*hostile.nonzero()):
            if max(abs(int(y) - int(bl.y)), abs(int(x) - int(bl.x))) <= 5:
                return None
        food = self._food()
        if food is None:
            return None
        y0, x0 = int(bl.y), int(bl.x)
        pets = []
        for y, x in zip(*utils.isin(agent.glyphs, G.PETS).nonzero()):
            name = MON.permonst(agent.glyphs[y, x]).mname
            # Melee hit must come from an adjacent pet of the reported species.
            if name == attack.group(1).lower() and \
                    max(abs(int(y) - y0), abs(int(x) - x0)) == 1:
                pets.append((int(y), int(x)))
        if len(pets) != 1:
            return None
        direction = self._line_to(*pets[0])
        return (food, direction) if direction is not None else None

    @Strategy.wrap
    def strategy(self):
        try:
            plan = self._plan()
        except Exception:
            plan = None
        if plan is None:
            yield False
            return
        yield True
        food, (dy, dx) = plan
        agent = self.agent
        self.last_throw = agent.blstats.time
        direction = agent.calc_direction(agent.blstats.y, agent.blstats.x,
                                         agent.blstats.y + dy, agent.blstats.x + dx)
        agent.log(f"PET feeding {food.objs[0].name} toward {direction}")
        agent.fire(food, direction)

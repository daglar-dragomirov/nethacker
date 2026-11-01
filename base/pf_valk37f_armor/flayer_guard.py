"""mind flayer lane (jf_config.FLAYER_GUARD): keep a (master) mind flayer's tentacles from ending the dive by
"brainlessness".

A mind flayer (monst.c: 9HD, speed 12, flies, AC 5, MR 90) has a weapon attack and one AT_TENT AD_DRIN tentacle; a
master mind flayer (13HD, AC 0) has five. Every tentacle that hits (mhitu.c AD_DRIN) eats our brain unless a worn
helmet blocks it -- rn2(8): 7 times in 8 -- and eat.c eat_brains kills outright when our Int is already at its minimum
(3) before the bite; otherwise Int drops by rnd(2) and we forget 25% of the map and of our object discoveries. A
Valkyrie starts with Int ~7-9 and no helmet, so a straight melee with a mind flayer (~40 HP: 5-6 of our turns) feeds it
4-5 tentacles: parent val-hum-neu-fem public seed 7 died so at Dlvl 29 and val-dwa-law-fem (dev) at Dlvl 25. The dive
files both flayers under RANGED_MONSTERS (dive._ignores_elbereth: the psychic blast), so its Elbereth rest and dig
Elbereths skip them and fight2 meleed them.
But monmove.c onscary() has no exemption for them: outside Gehennom an Elbereth under us scares them and a scared
monster never calls mattacku (dochug) -- no tentacle. Their psychic blast (dochug, 1 in 20 turns) only hurts a hero
whose telepathy it can lock onto (blind with telepathy, or extrinsic telepathy), which a seeing dive never is.

While a hostile flayer we can see is within 2 squares (it moves 12 like us: next turn it attacks) and its expected
brain bites over FLAYER_HORIZON turns (tentacles x 1/8 with a helmet, else x 1) reach the bites our current Int
survives at worst (-2 a bite), the guard takes the first of:
  1. a known wand of digging zapped down where a hole works (flayers have no M2_STALK: they don't follow);
  2. outside Gehennom, not already on an intact Elbereth: engrave Elbereth (capped per square);
  3. on our intact Elbereth: hold it -- dig_first digs on from it when it can (digging is no attack), else we search
     instead of letting fight2 swing (uhitm.c: attacking from Elbereth erases it), FLAYER_HOLD_TURNS per level;
  4. on an up staircase (no Elbereth possible, e.g. Gehennom): climb.
An Elbereth that failed to hold (our brain eaten while standing on it) is not tried again on that level. Not while
hallucinating (the names lie) or blind (Elbereth can't be read back), engulfed, or floating over the castle moat. A
safe low-HP prayer goes first (mino_guard._prayer_first). Every action is logged 'FLAYER ...'.
"""
from . import jf_config, utils
from .glyph import G
from .level import Level
from .strategy import Strategy

GEHENNOM = 1               # dungeon number (dive_logic.GEHENNOM)
FLAYER_RANGE = 2           # a flayer this close (Chebyshev) attacks on its next move
FLAYER_HORIZON = 8         # our turns to kill a flayer in melee (~40 / ~60 HP at ~9 a hit)
FLAYER_HOLD_TURNS = 60     # searches on our Elbereth per level before the normal fight takes over
ELBERETH_TRIES = 3         # engravings per square (dust can come out garbled)
INT_MIN = 3                # attrib.c ATTRMIN(A_INT) for every playable race
_TENTACLES = {'mind flayer': 1, 'master mind flayer': 5}
_BRAIN = 'Your brain is eaten!'


def _cheb(a, b):
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1])))


# hypothesis: a flayer that can eat our brain to death over a melee is better answered by a hole, an Elbereth it
# respects (held without swinging) or the stairs than by fight2 -- 'killed by brainlessness' ended parent val-hum-neu s7
# (Dlvl 29) and a val-dwa-law dev game (Dlvl 25).
# sources: NetHack 3.6.6 src/mhitu.c AD_DRIN, src/eat.c eat_brains, src/monmove.c onscary/dochug, src/uhitm.c
# (attacking from Elbereth erases it); https://nethackwiki.com/wiki/Mind_flayer ; https://nethackwiki.com/wiki/Elbereth
class FlayerGuard:
    def __init__(self, dive, mino):
        self.dive = dive
        self.agent = dive.agent
        self.mino = mino
        self._tries = {}         # (level key, (y, x)) -> Elbereths engraved there
        self._held = {}          # level key -> searches held on Elbereth
        self._failed = set()     # level keys where an Elbereth under us did not stop a brain bite
        self._noted = -1         # last turn whose message was parsed

    # ------------------------------------------------------------------ state

    def _in_scope(self):
        agent = self.agent
        prop = agent.character.prop
        if prop.hallu or prop.blind or prop.polymorph:
            return False
        if utils.any_in(agent.glyphs, G.SWALLOW):
            return False
        if self.dive.levitating() or self.dive.castle._floating():
            return False
        return True

    def _on_elbereth(self):
        return (self.agent.inventory.engraving_below_me or '').lower() == 'elbereth'

    def _note(self):
        """A brain bite while an Elbereth lies under us: it doesn't hold here (Gehennom-like rules, a displaced
        image, an unseen second flayer) -- no more Elbereths on this level."""
        agent = self.agent
        turn = int(agent.blstats.time)
        if turn == self._noted:
            return
        self._noted = turn
        if _BRAIN in (agent.message or '') and self._on_elbereth():
            key = agent.current_level().key()
            if key not in self._failed:
                self._failed.add(key)
                agent.log(f'FLAYER brain eaten on Elbereth at T{turn}: no more Elbereths on this level')

    def _danger(self):
        """The flayers within FLAYER_RANGE when their bites over FLAYER_HORIZON turns could kill us, else []."""
        agent = self.agent
        bl = agent.blstats
        pos = (int(bl.y), int(bl.x))
        flayers = [m for m in agent.get_visible_monsters()
                   if getattr(m[3], 'mname', '') in _TENTACLES and _cheb((m[1], m[2]), pos) <= FLAYER_RANGE]
        if not flayers:
            return []
        tentacles = sum(_TENTACLES[m[3].mname] for m in flayers)
        helm = agent.inventory.items.helm is not None
        expected = tentacles * (1 / 8 if helm else 1) * FLAYER_HORIZON
        # bites our Int survives at worst: rnd(2) each, the one at INT_MIN kills
        bites = (max(int(bl.intelligence), INT_MIN) - INT_MIN + 1) // 2 + 1
        return flayers if expected >= bites else []

    # ------------------------------------------------------------------ the plan

    def _plan(self):
        """(kind, arg, why, flayers) or None. Side-effect free apart from message notes (runs as a condition)."""
        if not jf_config.FLAYER_GUARD or not self._in_scope():
            return None
        self._note()
        flayers = self._danger()
        if not flayers or self.mino._prayer_first():
            return None
        agent = self.agent
        dive = self.dive
        bl = agent.blstats
        level = agent.current_level()
        key = level.key()
        pos = (int(bl.y), int(bl.x))
        # 1. a hole
        if self.mino._diggable():
            wand = dive._dig_wand()
            if wand is not None and dive._wand_escape(wand) is not None:
                return ('zapdown', wand, 'known wand of digging', flayers)
        elbereth_ok = level.dungeon_number != GEHENNOM and key not in self._failed
        if elbereth_ok:
            # 3. hold our Elbereth (dig_first digs on from it when it can)
            if self._on_elbereth():
                if dive._escape_next() is not None:
                    return None
                if self._held.get(key, 0) < FLAYER_HOLD_TURNS:
                    return ('hold', None, 'on Elbereth', flayers)
            # 2. write one
            elif agent.can_engrave() and self._tries.get((key, pos), 0) < ELBERETH_TRIES:
                return ('engrave', None, 'Elbereth', flayers)
        # 4. the up staircase under us (flayers don't follow: no M2_STALK)
        if level.dungeon_number != Level.SOKOBAN:
            ups = self.mino._ups()
            if ups and ups[0][0] == 0:
                return ('climb', None, 'on the up stairs', flayers)
        return None

    # ------------------------------------------------------------------ acting

    def _act(self, plan):
        agent = self.agent
        kind, arg, why, flayers = plan
        bl = agent.blstats
        key = agent.current_level().key()
        pos = (int(bl.y), int(bl.x))
        agent.log(f'FLAYER {kind} ({why}): Int {bl.intelligence}, helm {agent.inventory.items.helm is not None}, '
                  f'hp {bl.hitpoints}/{bl.max_hitpoints}, {[(m[3].mname, int(m[1]), int(m[2])) for m in flayers]}, '
                  f'depth {bl.depth}')
        if kind == 'zapdown':
            self.dive._escape_act(('zap', arg))
        elif kind == 'engrave':
            self._tries[(key, pos)] = self._tries.get((key, pos), 0) + 1
            agent.engrave('Elbereth')
        elif kind == 'hold':
            self._held[key] = self._held.get(key, 0) + 1
            agent.search(1)
        elif kind == 'climb':
            agent.move('<')

    def strategy(self):
        def f():
            plan = self._plan()
            if plan is None:
                yield False
                return
            yield True
            self._act(plan)

        return Strategy(f)

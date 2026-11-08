# REUSES: #401 (this port, +0.0065 over its parent on score/public/held-out/dev; never reached a root) -- node #447
# re-applies it on #441's WAND_RESERVE, whose kept wand of digging is exactly what the guard's first lane zaps down
# (a minotaur in view is a #441 reserve emergency anyway), and adds root #405's MINO_RAY_ROOM gate (no known
# lightning where its bounce comes back through us; jf_config.MINO_RAY_ROOM).
# hypothesis: (node #401) val-dwa-law-fem's engine has no minotaur lane; minotaurs killed it in 6/20 parent games on
# maze levels (Dlvl 25-29). This port of nhbot's MinoGuard (plus #383's MINO_UNSEEN invisible-minotaur recognition)
# answers a minotaur in view before its 3d10/3d10/2d8 lands. Details in the docstring below.
# sources: nhbot/mino_guard.py; /board/past_ideas/node-309.diff (#309/#194/#267/#270/#295/#185, the same port);
# #383 MINO_UNSEEN; NetHack 3.6.6 mkmaze.c, monmove.c onscary, mhitu.c hitmsg/stop_occupation;
# https://nethackwiki.com/wiki/Minotaur
"""minotaur lane (jf_config.MINO_GUARD): keep minotaurs from ending the dive -- in the filler mazes between Medusa and
the castle (mkmaze.c fill_empty_maze: rn2(3) minotaurs per level) and in the castle's own west maze.

hypothesis: pf_vk_s23 (val-dwa-law-fem's engine) has no minotaur-specific countermeasure anywhere outside the
castle's own landing square (castle_landing.LANDING_GUARD) and the adjacent-only castle_power.BREACH_MINO (currently
off, deep_poly_escape_strategy, castle-depth-only): on the open maze levels between Medusa and the castle -- where
nhbot's and nhbot_v3's own in-repo dev history (mino_guard.py docstring; /refs/history.md #87/#91/#167) shows most
of its maze deaths happen, 0-13 turns after the level landing -- a minotaur in view gets no response until fight2
or dig_first reacts to it like any other monster, by which point its 3d10/3d10/2d8 at to-hit 25+ (MR 0, ignores
Elbereth) has already cost 30-50 HP. Porting nhbot's proven MinoGuard -- a dedicated, highest-priority lane that
reaches for a known wand of digging/teleport/polymorph/sleep/death, the up stairs, a scroll of
genocide/taming/scare-monster, or an unknown wand/scroll gamble, before any blow lands -- should close the same
parity gap this run already closed for nhbot_v3 (node #167) and that minotaurs are, by a wide margin, the single
largest cause of death across all three identities (18/60 = 30% of /refs/parent-eval.json + parent-eval-extra.json
rows; val-dwa-law-fem alone lost 5/17 of its depth>=20 games to a minotaur even without this guard).

sources: nhbot/mino_guard.py (the full proven module this ports, including its own measured evidence: cmp-main
90-game baseline, 23/90 minotaur deaths, 7 of 17 dev-set ones within 0-13 turns of a maze landing); nhbot/jf_config.py
MINO_GUARD/MINO_TAME/MINO_DIG_GUARD/MINO_CASTLE_ZAP flags; pf_vk_s23/castle_power.py's own BREACH_MINO section
(breach_wand/zap_breach_wand/is_big_ignorer, reused here instead of porting nhbot's separate best_zap/zap_value
apparatus) and its docstring (27/61 castlebench deaths to a minotaur within 30 turns of the landing); NetHack 3.6.6
monst.c (minotaur: 15HD, speed 15, 3d10/3d10/2d8, MR 0), monmove.c onscary (Elbereth-ignorer), mhitu.c
stop_occupation (any attack interrupts digging); https://nethackwiki.com/wiki/Minotaur (guaranteed on every maze
level and in the castle's own maze; countered by taming/sleep/death/teleport/polymorph/genocide/scare-monster, all
decisive since it has no magic resistance); /refs/history.md #87/#91/#167 (the same port, independently proven
positive on nhbot_v3's held-out seeds each time) and #185 (this exact port into pf_vk_s23, independently measured
**kept** with a real held-out gain: 0.4182 vs its own parent's 0.4150, built on a disjoint ancestor set from this
chain's #169/#178 retreat-upstairs fix -- which only fires at castle depth and leaves the Medusa-to-castle filler
mazes, where most maze-level minotaur deaths actually happen, with no minotaur-specific answer at all); confirmed by
diffing this file against the already-proven source and against /refs/parent/pf_vk_s23 (no MINO_* symbol exists
there at all) so this is new capability for this chain, not a duplicate of #169/#178's narrower fix.
Simplifications from the nhbot source, all on dependencies pf_vk_s23 does not have: no HORN_SCARE/instrument
candidates (pf_vk_s23 has no opp_items.py); no reserved() wand reservation hook (no fight2 integration point for it
here); genocide's prompt answers are the fixed 'minotaur'/'H' default (no opp_items.proven_cursed cursed-stack
check); the four known/unknown in-line wand candidates (teleport/polymorph/sleep, death/sleep-or-death, cold/fire/
lightning, unknown gamble) collapse into two calls to pf_vk_s23's own castle_power.breach_wand, known first then
unknown, which already encodes the same stop-it-or-hurt-it priority order for this exact monster.
"""
import re

import nle.nethack as nh
from nle.nethack import actions as A

from . import castle_power, jf_config, power, utils
from . import objects as O
from .glyph import G
from .item import Item
from .level import Level
from .strategy import Strategy

MINO_RANGE = 6            # react to a minotaur in view this close (Chebyshev); beams reach 6-13, rays 7-13
MINO_CONSUME_RANGE = 5    # ...scrolls and self-teleports only this close: at first sight
MINO_STAIRS_STEPS = 2     # walk to an up staircase this many steps away
MINO_STAIRS_AVOID = 1000  # turns the '>' we climbed onto is avoided (dig down elsewhere instead)
MINO_ALERT_TURNS = 300    # after a minotaur sighting on a level, no rest there this long
MINO_RAY_SAFE_RUN = 6     # MINO_RAY_ROOM: free squares from us (the minotaur's included) a ray needs to die out:
                          # back on our square it has spent 2n+3 of its rn1(7,7) <= 13 range (zap.c dobuzz)
SLEEP_WINDOW = 150        # our sleep ray froze it for d(6,25) turns (zap.c sleep_monst), at most this long

_SCR = {n: O.from_name(n, nh.SCROLL_CLASS) for n in ('teleportation', 'genocide', 'scare monster', 'taming')}
_SLEEP_HIT = re.compile(r'The sleep ray hits (?:the )?minotaur')
_MINO_ACTS = re.compile(r'The minotaur (?:hits|misses|just misses|butts|bites)')
_NOTELEPORT = 'A mysterious force prevents you from teleporting'
GEHENNOM = 1   # dungeon number (dive_logic.GEHENNOM)
_PM_MINOTAUR = next(i for i in range(nh.NUMMONS) if nh.permonst(i).mname == 'minotaur')
_MINO_GLYPHS = [off + _PM_MINOTAUR for off in (nh.GLYPH_MON_OFF, nh.GLYPH_PET_OFF, nh.GLYPH_DETECT_OFF,
                                               nh.GLYPH_RIDDEN_OFF)]
_MINO_PERMONST = nh.permonst(_PM_MINOTAUR)
# hypothesis: MINO_UNSEEN -- an invisible minotaur (or any minotaur while we are blind) never shows a minotaur glyph,
# so the guard never fires and it hits for ~42 HP a turn until we die ('killed by an invisible minotaur': 326 of the
# board's 13500 games, ~7% of val-hum-neu-fem's). Its blows still name it: mhitu.c hitmsg prints AT_BUTT as "It
# butts!" when we can't see the attacker, and mattacku map_invisible()s an 'I' on its square. A minotaur's claw/claw/
# butt is the only butt there without a kick (unicorns) or bite (mumak), so an adjacent 'I' after such a blow is
# taken for it and the guard's plan (dig out, up stairs, teleport, genocide, scare monster, wands down the line)
# runs against it as against a seen one.
# sources: NetHack 3.6.6 mhitu.c (hitmsg AT_BUTT "%s butts!", mattacku map_invisible), monst.c (PM_MINOTAUR: AT_CLAW
# 3d10, AT_CLAW 3d10, AT_BUTT 2d8); end.c done_in_by ("invisible " for minvis); https://nethackwiki.com/wiki/Minotaur;
# https://nethackwiki.com/wiki/Invisible; /board/nodes/*.json death counts.
_UNSEEN_BUTT = re.compile(r'(?:^|[.!?] )It butts!')
_UNSEEN_OTHER = re.compile(r'(?:^|[.!?] )It (?:kicks|bites)!')   # a unicorn's / a mumak's butt comes with these
UNSEEN_TURNS = 20         # an 'I' next to us is taken for the minotaur this long after its last unseen butt


class MinoGuard:
    def __init__(self, dive):
        self.dive = dive
        self.agent = dive.agent
        dive.mino_guard = self
        self._seen = {}            # level key -> last turn a minotaur was in view
        self._asleep = {}          # (level key, (y, x)) -> turn our sleep ray hit a minotaur there
        self._noteleport = set()   # level keys where a teleport was refused
        self._read_glyphs = set()  # unknown scroll labels read by the guard (never twice)
        self._last_note = None
        self._step_blocked_until = -1
        self._blocked = {}         # (kind, item glyph) -> turn until which that action isn't planned
        self._attempts = {}        # (kind, item glyph) -> (turn, tries in that turn)
        self._unseen_butt = {}     # MINO_UNSEEN: level key -> last turn an unseen attacker butted us
        self._unseen_note = None

    # ------------------------------------------------------------------ state

    def alert(self):
        """A minotaur was in view on this level within MINO_ALERT_TURNS turns: no resting here."""
        if not jf_config.MINO_GUARD:
            return False
        t = self._seen.get(self.agent.current_level().key())
        return t is not None and self.agent.blstats.time - t <= MINO_ALERT_TURNS and self._diggable()

    def _in_scope(self):
        agent = self.agent
        level = agent.current_level()
        if level.dungeon_number not in (Level.DUNGEONS_OF_DOOM, GEHENNOM):
            return False
        prop = agent.character.prop
        if prop.polymorph or prop.hallu:
            return False
        if utils.any_in(agent.glyphs, G.SWALLOW):
            return False
        if self.dive.levitating() or self.dive.castle._floating():
            return False
        return True

    def _note(self):
        """Idempotent message parsing (runs on every check): our sleep ray froze a minotaur; a refused teleport."""
        agent = self.agent
        msg = agent.message or ''
        key = agent.current_level().key()
        stamp = (agent.step_count, key)
        if self._last_note == stamp:
            return
        self._last_note = stamp
        if _NOTELEPORT in msg:
            self._noteleport.add(key)
        if _MINO_ACTS.search(msg):
            last = max(msg.rfind('The minotaur hits'), msg.rfind('The minotaur misses'),
                       msg.rfind('The minotaur just misses'), msg.rfind('The minotaur butts'),
                       msg.rfind('The minotaur bites'))
            ray = msg.rfind('The sleep ray hits')
            if ray < last:
                self._asleep = {k: v for k, v in self._asleep.items() if k[0] != key}
        if _SLEEP_HIT.search(msg):
            for m in self._minos():
                self._asleep[(key, (m[1], m[2]))] = agent.blstats.time

    def _minos(self):
        """Minotaurs on the screen: [(chebyshev distance, y, x, permonst)], nearest first."""
        agent = self.agent
        bl = agent.blstats
        ys, xs = utils.isin(agent.glyphs, _MINO_GLYPHS).nonzero()
        out = []
        for y, x in zip(ys, xs):
            y, x = int(y), int(x)
            if (y, x) == (int(bl.y), int(bl.x)):
                continue
            if jf_config.MINO_TAME and (nh.glyph_is_pet(int(agent.glyphs[y, x])) or
                                        agent.monster_tracker.peaceful_monster_mask[y, x]):
                continue
            out.append((max(abs(y - int(bl.y)), abs(x - int(bl.x))), y, x, _MINO_PERMONST))
        out.extend(self._unseen_minos())
        out.sort(key=lambda m: m[0])
        return out

    def _unseen_minos(self):
        """MINO_UNSEEN: the 'I' squares next to us while an unseen attacker that butts (the minotaur's AT_BUTT, mhitu.c
        hitmsg 'It butts!') hit us on this level within UNSEEN_TURNS: [(1, y, x, permonst)]."""
        if not jf_config.MINO_UNSEEN:
            return []
        agent = self.agent
        key = agent.current_level().key()
        stamp = (agent.step_count, key)
        if self._unseen_note != stamp:
            self._unseen_note = stamp
            msg = agent.message or ''
            if _UNSEEN_BUTT.search(msg) and not _UNSEEN_OTHER.search(msg):
                self._unseen_butt[key] = agent.blstats.time
        t = self._unseen_butt.get(key)
        if t is None or agent.blstats.time - t > UNSEEN_TURNS:
            return []
        bl = agent.blstats
        y0, x0 = int(bl.y), int(bl.x)
        near = agent.glyphs[max(y0 - 1, 0):y0 + 2, max(x0 - 1, 0):x0 + 2] == nh.GLYPH_INVISIBLE
        ys, xs = near.nonzero()
        return [(1, int(y) + max(y0 - 1, 0), int(x) + max(x0 - 1, 0), _MINO_PERMONST) for y, x in zip(ys, xs)]

    def _frozen(self, m):
        t = self._asleep.get((self.agent.current_level().key(), (m[1], m[2])))
        return t is not None and self.agent.blstats.time - t <= SLEEP_WINDOW

    def _diggable(self):
        """This level can be holed (not the castle or another bottom, not the Valley's hardfloor)."""
        dive = self.dive
        level = self.agent.current_level()
        key = level.key()
        if key in dive.undiggable or key == dive.castle.castle_key or dive.in_valley() or \
                level.dungeon_number not in (Level.DUNGEONS_OF_DOOM, GEHENNOM):
            return False
        return True

    def _castle_evidence(self):
        """MINO_CASTLE_ZAP: the level has shown itself to be the castle before the dive recognised it -- below
        Medusa, or a refused dig here."""
        dive = self.dive
        key = self.agent.current_level().key()
        if key in dive.undiggable or key == dive.castle.castle_key:
            return True
        return bool(dive.below_medusa()) and key in getattr(dive, '_door_heard', {})

    def _dig_interrupter(self):
        """MINO_DIG_GUARD: a hostile next to us (not a minotaur) whose attacks will stop the dig occupation -- an
        Elbereth-ignorer, or any one while no intact Elbereth lies under us; None if a dig can go on."""
        agent = self.agent
        bl = agent.blstats
        y0, x0 = int(bl.y), int(bl.x)
        elbereth = not agent.character.prop.blind and \
            (agent.inventory.engraving_below_me or '').lower() == 'elbereth'
        for m in agent.get_visible_monsters():
            if getattr(m[3], 'mname', '') == 'minotaur' or max(abs(int(m[1]) - y0), abs(int(m[2]) - x0)) > 1:
                continue
            if not elbereth or self.dive._melee_ignores_elbereth(m[3]):
                return m
        return None

    def _teleport_ok(self):
        """Teleporting within this level works: filler mazes yes; the castle, Medusa's island, the Valley and
        Sokoban no."""
        dive = self.dive
        level = self.agent.current_level()
        key = level.key()
        if key in self._noteleport or key == dive.castle.castle_key or key == dive.medusa_level or \
                dive.in_valley() or level.dungeon_number == Level.SOKOBAN or self._maybe_castle():
            return False
        return True

    def _maybe_castle(self):
        """This may be the castle, not yet recognised (that takes a failed dig): the Dungeons at castle depth
        (CASTLE_SCARE_DEPTH, 25+), no castle known elsewhere, and we arrived inside its fall region."""
        dive = self.dive
        agent = self.agent
        level = agent.current_level()
        key = level.key()
        if level.dungeon_number != Level.DUNGEONS_OF_DOOM or agent.blstats.depth < jf_config.CASTLE_SCARE_DEPTH:
            return False
        castle = dive.castle.castle_key
        if castle is not None:
            return castle == key
        vkey, vpos = getattr(dive, '_visit_pos', (None, None))
        return vkey == key and vpos is not None and int(vpos[1]) <= 9

    def _prayer_first(self):
        """emergency_strategy (below us) would pray now: let it -- the prayer's 3 invulnerable turns and full HP
        come before any item (then the item from full HP)."""
        agent = self.agent
        bl = agent.blstats
        if agent.prayer_failed:
            return False
        xl = bl.experience_level
        low = bl.hitpoints < bl.max_hitpoints / (5 if xl < 6 else 6) or \
            (bl.hitpoints < 12 and bl.hitpoints < bl.max_hitpoints)
        if low and agent.is_safe_to_pray(500):
            return True
        return bool(jf_config.DESPERATE_PRAYER_GAP) and agent._critically_low_hp() and \
            agent.current_level().dungeon_number != GEHENNOM and self.dive.diving and bl.depth >= 5 and \
            agent.is_safe_to_pray(jf_config.DESPERATE_PRAYER_GAP)

    # ------------------------------------------------------------------ items

    def _scroll(self, name, cursed_ok=False):
        agent = self.agent
        for it in agent.inventory.items:
            if it.category == nh.SCROLL_CLASS and it.is_unambiguous() and it.object == _SCR[name] and \
                    (cursed_ok or it.status != Item.CURSED):
                return it
        return None

    def _unknown_scroll(self):
        """The unknown scroll most likely to end the fight: P(teleportation) (where teleports work) + P(scare
        monster) + P(taming) + P(genocide); (item, p) or (None, 0)."""
        agent = self.agent
        good = {_SCR['scare monster'], _SCR['taming'], _SCR['genocide']}
        if self._teleport_ok():
            good.add(_SCR['teleportation'])
        best, bp = None, 0.0
        for it in agent.inventory.items:
            if it.category != nh.SCROLL_CLASS or it.is_unambiguous() or it.glyphs[0] in self._read_glyphs:
                continue
            p = power.p_of(it, good)
            if p > bp:
                best, bp = it, p
        return best, bp

    # ------------------------------------------------------------------ geometry

    def _line(self, m):
        """(direction, distance, (sy, sx)) toward minotaur m if it is in a straight line within MINO_RANGE, else
        None."""
        bl = self.agent.blstats
        dy, dx = m[1] - int(bl.y), m[2] - int(bl.x)
        dist = max(abs(dy), abs(dx))
        if dist == 0 or dist > MINO_RANGE or not (dy == 0 or dx == 0 or abs(dy) == abs(dx)):
            return None
        sy, sx = (dy > 0) - (dy < 0), (dx > 0) - (dx < 0)
        return self.agent.calc_direction(bl.y, bl.x, bl.y + sy, bl.x + sx), dist, (sy, sx)

    def _free_run(self, sy, sx):
        """Walkable squares from us in direction (sy, sx) before a wall or the map's edge (unseen squares stop it)."""
        level = self.agent.current_level()
        y, x = int(self.agent.blstats.y), int(self.agent.blstats.x)
        h, w = level.walkable.shape
        n = 0
        while n < 20:
            y, x = y + sy, x + sx
            if not (0 <= y < h and 0 <= x < w) or not level.walkable[y, x]:
                break
            n += 1
        return n

    def _ups(self):
        """Up staircases on this level we could climb to escape: [(steps, (y, x))]."""
        agent = self.agent
        dive = self.dive
        level = agent.current_level()
        if level.dungeon_number == Level.SOKOBAN or agent.blstats.depth <= 1 or dive.in_valley():
            return []
        if jf_config.MEDUSA_NO_RETREAT and dive._up_leads_to_medusa():
            return []
        ups = {(int(y), int(x)) for y, x in zip(*utils.isin(level.objects, G.STAIR_UP).nonzero())}
        ups |= {(int(p[0]), int(p[1])) for p, dest in level.stair_destination.items()
                if dest[0][0] == level.dungeon_number and dest[0][1] < level.level_number}
        arr = getattr(dive, '_arrival_square', None)
        if arr is not None and arr[0] == level.key():
            ups.add((int(arr[1][0]), int(arr[1][1])))
        pos = (int(agent.blstats.y), int(agent.blstats.x))
        if pos in ups:
            return [(0, pos)]
        dis = agent.bfs()
        return sorted((int(dis[p]), p) for p in ups if dis[p] > 0)

    # ------------------------------------------------------------------ the plan

    def _plan(self):
        """The guard's next action (kind, arg, why) or None: the first candidate not blocked by the loop guard."""
        if not jf_config.MINO_GUARD or not (utils.isin(self.agent.glyphs, _MINO_GLYPHS).any() or
                                            self._unseen_minos()) or \
                not self._in_scope():
            return None
        turn = self.agent.blstats.time
        for plan in self._candidates():
            if self._blocked.get(self._block_key(plan), -1) < turn:
                return plan
        return None

    @staticmethod
    def _block_key(plan):
        kind, arg, _ = plan
        item = arg[0] if isinstance(arg, tuple) and arg and hasattr(arg[0], 'glyphs') else arg
        return (kind, item.glyphs[0] if hasattr(item, 'glyphs') else None)

    def _candidates(self):
        """The guard's actions (kind, arg, why), best first (see the module docstring)."""
        agent = self.agent
        dive = self.dive
        self._note()
        minos = self._minos()
        if not minos:
            return
        bl = agent.blstats
        key = agent.current_level().key()
        self._seen[key] = bl.time
        awake = [m for m in minos if not self._frozen(m)]
        diggable = self._diggable()
        if not awake:
            if diggable and minos[0][0] <= MINO_RANGE and self._dig_action() is not None and \
                    not (jf_config.MINO_DIG_GUARD and self._dig_interrupter() is not None):
                yield ('dig', None, f'minotaur asleep at {minos[0][0]}')
            return
        near = awake[0][0]
        if near > MINO_RANGE:
            return
        if self._prayer_first():
            return
        if dive.on_scare_scroll():
            if diggable and self._dig_action() is not None:
                yield ('dig', None, 'on a scroll of scare monster')
            return
        adjacent = near <= 1
        consume = near <= MINO_CONSUME_RANGE or adjacent
        lines = [(self._line(m), m) for m in awake]
        lines = [(ln, m) for ln, m in lines if ln is not None]
        # 1. a known wand of digging down (MINO_CASTLE_ZAP: not where the level showed itself to be the castle)
        if diggable and not (jf_config.MINO_CASTLE_ZAP and self._castle_evidence()):
            wand = dive.digging_wand()
            if wand is not None and dive._wand_escape(wand) is not None:
                yield ('zapdown', wand, 'known wand of digging')
        # 1a. MINO_TAME: a known scroll of taming with the minotaur next to us -- it never resists (MR 0)
        if jf_config.MINO_TAME and adjacent:
            scroll = self._scroll('taming')
            if scroll is not None:
                yield ('read', scroll, 'known taming, minotaur adjacent')
        # 2. a known wand at it in line (sleep/death/teleportation/polymorph, then striking/fire/cold/lightning/
        # magic missile/slow monster) -- castle_power's own BREACH_MINO priority order for this exact monster
        if lines:
            (direction, dist, (sy, sx)), m = lines[0]
            # MINO_RAY_ROOM: no known lightning where its bounce comes back through us (see jf_config)
            skip = ('lightning',) if jf_config.MINO_RAY_ROOM and self._free_run(sy, sx) < MINO_RAY_SAFE_RUN else ()
            wand, why = castle_power.breach_wand(agent, unknown_ok=False, skip=skip)
            if wand is not None:
                yield ('zap', (wand, direction, m), f'breach known ({why}) at {dist}')
        # 3. on an up staircase
        ups = self._ups()
        if ups and ups[0][0] == 0 and near <= MINO_CONSUME_RANGE:
            yield ('climb', None, 'on the up stairs')
        teleport = self._teleport_ok()
        # 4. teleport ourselves away (a known wand at us, a known scroll)
        if consume and teleport:
            for it in agent.inventory.items:
                if it.is_wand() and it.is_unambiguous() and it.object == O.from_name('teleportation', nh.WAND_CLASS) \
                        and not power._empty(agent, it):
                    yield ('zapself', it, 'known teleportation at ourselves')
                    break
            scroll = self._scroll('teleportation')
            if scroll is not None and not agent.character.prop.blind:
                yield ('read', scroll, 'known teleportation')
        # 5. genocide (not while confused: that genocides us)
        if consume and not agent.character.prop.confusion and not agent.character.prop.blind:
            scroll = self._scroll('genocide')
            if scroll is not None:
                yield ('read', scroll, 'known genocide')
        # 6. scare monster: drop it and dig from it
        if consume and diggable:
            scroll = self._scroll('scare monster', cursed_ok=True)
            if scroll is not None and agent.current_level().objects[bl.y, bl.x] not in G.STAIR_UP and \
                    agent.current_level().objects[bl.y, bl.x] not in G.STAIR_DOWN:
                yield ('drop_scare', scroll, 'known scare monster')
        # 7. an up staircase a step or two away
        if ups and 0 < ups[0][0] <= MINO_STAIRS_STEPS and consume and bl.time >= self._step_blocked_until and \
                not agent.in_pit() and (not adjacent or bl.hitpoints >= 0.5 * bl.max_hitpoints):
            yield ('step_up', ups[0][1], f'up stairs {ups[0][0]} steps away')
        # 8. an unknown wand at it: the best P(stop/hurt it) left (castle_power.breach_wand's unknown gamble)
        if lines and consume:
            (direction, dist, _), m = lines[0]
            wand, why = castle_power.breach_wand(agent, unknown_ok=True)
            if wand is not None:
                yield ('zap', (wand, direction, m), f'breach unknown ({why}) at {dist}')
        # 9. an unknown scroll where a teleport would work
        if teleport and consume and not agent.character.prop.blind and not agent.character.prop.confusion:
            scroll, p = self._unknown_scroll()
            if scroll is not None and p > 0:
                yield ('read', scroll, f'unknown scroll P(save)={p:.2f}')
        return

    def _dig_action(self):
        """What 'dig out now' would do: ('wand', wand) / ('pick', tool) / None."""
        dive = self.dive
        agent = self.agent
        bl = agent.blstats
        wand = dive.digging_wand()
        if wand is not None and dive._wand_escape(wand) is not None and \
                not (jf_config.MINO_CASTLE_ZAP and self._castle_evidence()):
            return ('wand', wand)
        tool = dive.digging_tool()
        if tool is None or agent.blstats.time < dive._dig_blocked_until:
            return None
        if tool.object == O.from_name('dwarvish mattock') and agent.inventory.items.off_hand is not None:
            return None
        max_wet = dive._dig_max_wet() or 0
        on_stairs = (bl.y, bl.x) in agent.current_level().stair_destination
        if dive._in_own_pit() or (not on_stairs and dive._diggable_spot(bl.y, bl.x, max_wet)):
            return ('pick', tool)
        return None

    # ------------------------------------------------------------------ acting

    def _act(self, plan):
        agent = self.agent
        dive = self.dive
        kind, arg, why = plan
        bkey = self._block_key(plan)
        t, n = self._attempts.get(bkey, (None, 0))
        n = n + 1 if t == agent.blstats.time else 1
        self._attempts[bkey] = (agent.blstats.time, n)
        if n >= 3:
            self._blocked[bkey] = agent.blstats.time + 3
            agent.log(f'MINO {bkey} refused 3 times at T{agent.blstats.time}: blocked for 3 turns')
        bl = agent.blstats
        hp = f'hp {bl.hitpoints}/{bl.max_hitpoints}'
        key = agent.current_level().key()
        if kind == 'dig':
            what = self._dig_action()
            agent.log(f'MINO dig out ({why}), {hp}')
            if what is None:
                return
            if what[0] == 'wand':
                dive._escape_act(('zap', what[1]))
            else:
                dive.dig_with_tool(what[1])
            return
        if kind == 'zapdown':
            agent.log(f'MINO zapping {arg.text!r} down ({why}), {hp}')
            dive._escape_act(('zap', arg))
            return
        if kind == 'climb':
            agent.log(f'MINO up the stairs ({why}), {hp}')
            agent.move('<')
            if agent.current_level().key() != key:
                dive._avoid_stairs_until[(agent.current_level().key(), (agent.blstats.y, agent.blstats.x))] = \
                    agent.blstats.time + MINO_STAIRS_AVOID
            return
        if kind == 'step_up':
            agent.log(f'MINO to the up stairs at {arg} ({why}), {hp}')
            start = (bl.y, bl.x)
            try:
                agent.go_to(arg[0], arg[1], max_steps=1)
            finally:
                if (agent.blstats.y, agent.blstats.x) == start:
                    self._step_blocked_until = agent.blstats.time + 5
            return
        if kind == 'zap':
            wand, direction, m = arg
            if not wand.is_unambiguous():
                agent._last_resort_zapped.add(wand.glyphs[0])
            agent.log(f'MINO zapping {wand.text!r} {direction} at the minotaur at {(m[1], m[2])} ({why}), {hp}')
            agent.zap(wand, direction)
            agent.log(f'MINO zap -> {(agent.message or "")[:160]!r}')
            if 'Nothing happens' in (agent.message or '') or 'You wrest' in (agent.message or ''):
                agent.inventory.empty_wands.add(wand.text)
            self._note()
            agent.inventory.items.update(force=True)
            return
        if kind == 'zapself':
            agent.log(f'MINO zapping {arg.text!r} at ourselves ({why}), {hp}')
            agent.zap(arg, '.')
            agent.log(f'MINO zap -> {(agent.message or "")[:160]!r}')
            self._note()
            agent.inventory.items.update(force=True)
            return
        if kind == 'read':
            self._read(arg, why)
            return
        if kind == 'drop_scare':
            agent.log(f'MINO dropping {arg.text!r} ({why}), {hp}')
            pos = (bl.y, bl.x)
            dive._scare_spot = (key, pos)
            dive._scare_drop_turn = bl.time
            agent.inventory.drop(arg, 1)
            agent.inventory._note_dropped([arg], [1], force=True)
            return
        raise ValueError(kind)

    def _read(self, item, why):
        """Read a scroll, answering what it may ask: genocide ('minotaur'; a blessed one's class 'H'), the identify
        menu (power_route's picks), a stinking cloud's aim and a charging scroll (declined)."""
        agent = self.agent
        from . import power_route
        if not item.is_unambiguous():
            self._read_glyphs.add(item.glyphs[0])
        letter = agent.inventory.items.get_letter(item)
        bl = agent.blstats
        agent.log(f'MINO reading {item.text!r} ({letter}): {why}, hp {bl.hitpoints}/{bl.max_hitpoints}')
        menu_pages = {}
        answered = set()

        def gen():
            if 'What do you want to read?' not in agent.single_message:
                return
            yield letter
            for _ in range(60):
                obs = agent._observation
                misc = obs['misc']
                top = ' '.join(bytes(line).decode('latin-1').replace('\0', ' ') for line in obs['tty_chars'][:2])
                msg = (agent.single_message or '') + ' ' + top
                head = msg + ' ' + ' '.join(agent.single_popup[:3])
                single = agent.single_message or ''
                if 'do you want to genocide' in single and 'monster' not in answered:
                    answered.add('monster')
                    for k in 'minotaur' + '\r':
                        yield k
                    continue
                if 'class of monsters do you wish to genocide' in single and 'class' not in answered:
                    answered.add('class')
                    for k in 'H' + '\r':
                        yield k
                    continue
                if 'What would you like to identify' in head:
                    keys = power_route._identify_step(agent, menu_pages)
                    if keys is None:
                        yield A.Command.ESC
                        continue
                    if keys.endswith('\r'):
                        menu_pages.clear()
                    for k in keys:
                        yield k
                    continue
                if 'Where do you want to center' in msg or 'What do you want to charge?' in msg:
                    yield A.Command.ESC
                    continue
                if misc[2] or '--More--' in top:
                    yield ' '
                    continue
                return

        with agent.atom_operation():
            agent.step(A.Command.READ, gen())
        agent.log(f'MINO read -> {(agent.message or "")[:200]!r}')
        self._note()
        agent.inventory.items.update(force=True)

    def strategy(self):
        def f():
            plan = self._plan()
            if plan is None:
                yield False
                return
            yield True
            self._act(plan)

        return Strategy(f)

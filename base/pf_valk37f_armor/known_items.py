# hypothesis: KNOWN_ITEMS for val-dwa-law-fem -- the dwarf engine is the only one with no known-item emergency layer:
# a KNOWN teleport/digging/healing/sleep/striking item used in mortal danger (critical HP or a burst that the next
# exchange repeats) turns its held-item deaths (soldier and elf-lord bursts, leocrottas, trolls in the filler levels)
# into a continued dive instead of an unknown-item gamble or a death with the item unused
# sources: nhbot/known_items.py + nhbot_v3/known_items.py (the human engines' guard incl. KNOWN_ITEMS_TARGET, ported
#   here); /board/past_ideas/node-456.diff, node-465.diff, node-476.diff (earlier pf ports, never in a root);
#   https://nethackwiki.com/wiki/Escape_item ; https://nethackwiki.com/wiki/Standard_strategy ("use your escape items
#   before you are at 1 HP"); https://nethackwiki.com/wiki/Scroll_of_teleportation ;
#   https://nethackwiki.com/wiki/Wand_of_digging ; NetHack 3.6.6 zap.c buzz() (ray range rn1(7,7), -2 per monster hit:
#   a wall behind an adjacent target bounces it back through us; striking is a beam), zap.c zhitm() resistances,
#   makemon.c mstrength() (target ranking), mon.c setmangry (no zap at a monster our Elbereth scares)
"""dive-audit lane (jf_config.KNOWN_ITEMS): in mortal danger while diving, use the KNOWN item that ends the danger
before emergency_strategy's last resort gambles on unknown ones.

This engine (val-dwa-law-fem) had no way to spend a known escape or attack item in a losing fight: the last resort
(agent.emergency_strategy) tries only UNKNOWN wands, potions and scrolls (plus a known wand of digging at critically
low HP), fight2 zaps only ray wands (never striking, a beam, never sleep), nothing reads a known scroll of teleportation
or zaps a known wand of teleportation at ourselves, and the last resort waits for pray.c's critically low HP (1/7 of
max), which a 20-40-a-turn attacker (minotaur, elf-lord volley, soldier group) skips straight over. nhbot/nhbot_v3
ship this guard (77 of 171 of their logged deaths held a known escape or attack item they never used); the dwarf's
engine never got it. A minotaur in view is left to mino_guard (MINO_GUARD), whose lane runs before this one: the
two guards never act on the same fight.

While diving (the Dungeons, the Mines, Gehennom), not polymorphed, engulfed, afloat or overtaxed, with a hostile next to
us -- or hurt this badly with one within RANGED_REACH -- and either
  (a) critically low HP (agent._critically_low_hp, the last resort's trigger), or
  (b) a burst: the HP lost over the last KNOWN_ITEMS_BURST_TURNS turns is at least what is left, below
      KNOWN_ITEMS_BURST_FRAC of max HP (the next such exchange kills us),
and no emergency prayer due (that goes first: its invulnerable turns and full HP beat any item), the guard takes the
first of:
  1. the up staircase we stand on, unless an M2_STALK monster next to us would follow;
  2. a known scroll of teleportation where teleports work (never a known-cursed one, WISH_TELEPORT_ROUTE's stack or
     with teleport control known), never with unpaid shop goods in the pack;
  3. a known wand of teleportation at ourselves (the same levels);
  4. a known wand of digging down, unless an M2_STALK monster next to us would follow through the hole;
  5. a known potion of full or extra healing (plain healing only at critically low HP);
  6. at the strongest attacker next to us: a known wand of sleep (a ray: needs a free run behind the target), a known
     wand of striking (a beam), cold (a Valkyrie resists its bounce; not a COLD_RESERVE wand), fire, lightning /
     magic missile with room -- never a type the target resists (zap.c zhitm).
No zap in Minetown or with a peaceful on the line, nor at a monster an intact Elbereth under us scares (mon.c
setmangry: 'You feel like a hypocrite', the engraving deleted). Every action is logged 'KNOWN_ITEMS ...'.
"""
import nle.nethack as nh

from . import castle_power, jf_config, utils
from .character import Character
from .combat.monster_utils import WEAK_MONSTERS
from .glyph import G, MON
from .item import Item, flatten_items
from .level import Level
from .strategy import Strategy

GEHENNOM = 1              # dungeon number (dive_logic.GEHENNOM)
RANGED_REACH = 7          # a burst with nothing next to us counts when a hostile is this close (wands, arrows, breath)
CASTLE_WEST_X = 10        # castle.des levregion x 1-10: a fall onto an unrecognised castle lands west of this
MR_SLEEP = 0x04           # monflag.h
_W = castle_power._W
_NOTELEPORT = 'A mysterious force prevents you from teleporting'


def _cheb(a, b):
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1])))


class KnownItemsGuard:
    def __init__(self, dive, mino=None):
        self.dive = dive
        self.mino = mino
        self.agent = dive.agent
        self._attempts = {}     # (kind, item glyph) -> (turn, tries in that turn)
        self._blocked = {}      # (kind, item glyph) -> turn until which that action isn't planned
        self._noteleport = set()  # level keys where a teleport was refused
        self.uses = 0           # actions taken (logged)

    # ------------------------------------------------------------------ state

    def _in_scope(self):
        agent = self.agent
        dive = self.dive
        if not dive.diving:
            return False
        level = agent.current_level()
        if level.dungeon_number not in (Level.DUNGEONS_OF_DOOM, Level.GNOMISH_MINES, GEHENNOM):
            return False
        if agent.character.prop.polymorph:
            return False   # a form's HP is a buffer
        if utils.any_in(agent.glyphs, G.SWALLOW):
            return False   # engulfed: engulfed_fight
        if dive.levitating() or dive.castle._floating():
            return False   # over the moat: the crossing's business
        if agent.blstats.carrying_capacity >= 4:
            return False   # overtaxed: zapping, reading and quaffing are refused without a turn
        deadly = int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION]) & (
            nh.BL_MASK_STONE | nh.BL_MASK_SLIME | nh.BL_MASK_STRNGL | nh.BL_MASK_FOODPOIS | nh.BL_MASK_TERMILL)
        if deadly:
            return False   # emergency_strategy's lizard / prayer cure comes first
        return True

    def _prayer_first(self):
        """emergency_strategy (below us) would pray now: let it -- the prayer's invulnerable turns and full HP come
        before any item. Mirrors its low-HP rule (DT6A's, EXACT_PRAYER off), its hunger prayers and the last resort's
        DESPERATE_PRAYER_GAP prayer."""
        agent = self.agent
        bl = agent.blstats
        if agent.prayer_failed:
            return False
        xl = bl.experience_level
        low = agent._critically_low_hp() or bl.hitpoints < bl.max_hitpoints / (5 if xl < 6 else 6) or \
            (bl.hitpoints < 12 and bl.hitpoints < bl.max_hitpoints)
        if low and agent.is_safe_to_pray(500):
            return True
        if agent.fainting_prayer_due() or agent.threat_prayer_due():
            return True
        return bool(jf_config.DESPERATE_PRAYER_GAP) and agent._critically_low_hp() and \
            agent.current_level().dungeon_number != GEHENNOM and self.dive.diving and bl.depth >= 5 and \
            agent.is_safe_to_pray(jf_config.DESPERATE_PRAYER_GAP)

    def _danger(self):
        """(adjacent hostiles, 'critical' | 'burst', HP lost) when the guard should act, else None."""
        agent = self.agent
        bl = agent.blstats
        hp, maxhp = int(bl.hitpoints), int(bl.max_hitpoints)
        critical = agent._critically_low_hp()
        prev = [h for t, h in self.dive._hp_history if t >= bl.time - jf_config.KNOWN_ITEMS_BURST_TURNS]
        loss = (max(prev) - hp) if prev else 0
        burst = loss > 0 and loss >= hp and hp < jf_config.KNOWN_ITEMS_BURST_FRAC * maxhp
        if not (critical or burst):
            return None
        pos = (int(bl.y), int(bl.x))
        monsters = [m for m in agent.get_visible_monsters() if getattr(m[3], 'mname', '') not in WEAK_MONSTERS]
        adjacent = [m for m in monsters if _cheb((m[1], m[2]), pos) <= 1]
        if not adjacent and not (loss > 0 and any(_cheb((m[1], m[2]), pos) <= RANGED_REACH for m in monsters)):
            return None
        if adjacent and self._on_elbereth() and not any(self.dive._melee_ignores_elbereth(m[3]) for m in adjacent) and \
                bl.time - self.dive._hurt_on_elbereth > 2:
            # an intact Elbereth under us holds everything next to us and nothing has hurt us through it
            return None
        return adjacent, ('critical' if critical else 'burst'), loss

    def _minotaur_fight(self):
        """A minotaur (seen, or the unseen butter next to us) is mino_guard's: its lane runs first and owns that fight."""
        mino = self.mino
        if mino is None or not jf_config.MINO_GUARD or not mino._in_scope():
            return False
        return bool(mino._minos())

    def _on_elbereth(self):
        """An Elbereth under us that we can read back (not while blind: dust can't be felt)."""
        agent = self.agent
        return not agent.character.prop.blind and (agent.inventory.engraving_below_me or '').lower() == 'elbereth'

    def _teleport_ok(self):
        """Teleporting within this level works: not Sokoban, the Valley, Medusa's island or the castle (their .des
        FLAGS: noteleport), nor a level that refused before. Below Medusa's depth the dive only knows the castle after a
        refused dig, so there a teleport is only tried once Medusa's level is known to be above us and this is not
        the castle, or a fall that could be the castle's west landing region."""
        dive = self.dive
        agent = self.agent
        level = agent.current_level()
        key = level.key()
        if key in self._noteleport or level.dungeon_number == Level.SOKOBAN or dive.in_valley():
            return False
        if level.dungeon_number != Level.DUNGEONS_OF_DOOM:
            return True
        castle = dive.castle.castle_key
        if key == dive.medusa_level or key == castle:
            return False
        from .dive_logic import MEDUSA_MIN_DEPTH
        if agent.blstats.depth < MEDUSA_MIN_DEPTH:
            return True
        if not dive.below_medusa():
            return False   # Medusa's level unrecognised (every variant is noteleport), or not yet passed
        return castle is not None or int(agent.blstats.x) >= CASTLE_WEST_X

    def _diggable(self):
        """This level can be holed (not the castle or another bottom, not the Valley's hardfloor, not Sokoban)."""
        dive = self.dive
        level = self.agent.current_level()
        key = level.key()
        if key in dive.undiggable or key == dive.castle.castle_key or dive.in_valley() or \
                level.dungeon_number not in (Level.DUNGEONS_OF_DOOM, Level.GNOMISH_MINES, GEHENNOM):
            return False
        return True

    # ------------------------------------------------------------------ items

    def _wand(self, names):
        """A known, not-empty top-level wand of one of `names` (in that order): (item, name) or (None, None)."""
        from . import power
        agent = self.agent
        for name in names:
            obj = _W[name]
            for it in agent.inventory.items:
                if it.is_wand() and it.is_unambiguous() and it.object == obj and not power._empty(agent, it):
                    return it, name
        return None, None

    def _sleep_or_death(self):
        """An engrave-tested wand that is sleep or death ('The bugs on the floor stop moving!'): either stops it."""
        from . import power
        agent = self.agent
        pair = {_W['sleep'], _W['death']}
        for it in agent.inventory.items:
            if it.is_wand() and not it.is_unambiguous() and it.objs and set(it.objs) <= pair and \
                    not power._empty(agent, it):
                return it
        return None

    def _tele_scroll(self):
        """A known scroll of teleportation we may spend: not known cursed (power_route's level-teleport tickets), not
        WISH_TELEPORT_ROUTE's wished stack, and not with teleport control known (the TC route's business)."""
        agent = self.agent
        if getattr(agent, '_tele_letter', None) is not None:
            return None
        from . import power_route
        try:
            if power_route.tc_known(agent):
                return None
            reserved = power_route.cursed_tele_scrolls(agent)
        except Exception:
            return None
        for it in power_route.tele_scrolls(agent):
            if it in agent.inventory.items and it.status != Item.CURSED and it not in reserved:
                return it
        return None

    def _heal_potion(self, critical):
        names = ('full healing', 'extra healing') + (('healing',) if critical else ())
        agent = self.agent
        for name in names:
            for it in agent.inventory.items:
                if it.category == nh.POTION_CLASS and it.is_unambiguous() and it.object.name == name:
                    return it
        return None

    def _unpaid(self):
        """Shop goods in the pack: a teleport out of the shop is theft."""
        return any(it.shop_status == Item.UNPAID for it in flatten_items(self.agent.inventory.items))

    def _ups_here(self):
        """We stand on an up staircase we may climb (not Sokoban, Dlvl 1, the Valley, nor onto Medusa's '>')."""
        agent = self.agent
        dive = self.dive
        level = agent.current_level()
        if level.dungeon_number == Level.SOKOBAN or agent.blstats.depth <= 1 or dive.in_valley():
            return False
        if jf_config.MEDUSA_NO_RETREAT and dive._up_leads_to_medusa():
            return False
        castle = dive.castle.castle_key
        if jf_config.CASTLE_NO_RETREAT and castle is not None and level.key() == castle:
            return False
        return level.objects[agent.blstats.y, agent.blstats.x] in G.STAIR_UP

    def _line_hits_peaceful(self, dy, dx):
        """A peaceful (a watchman, a shopkeeper) in view on our zap line within a ray's reach."""
        agent = self.agent
        mask = agent.monster_tracker.peaceful_monster_mask
        h, w = mask.shape
        y, x = int(agent.blstats.y), int(agent.blstats.x)
        for _ in range(13):
            y, x = y + dy, x + dx
            if not (0 <= y < h and 0 <= x < w):
                break
            if mask[y, x]:
                return True
        return False

    def _free_run_behind(self, target, dy, dx):
        """Walkable squares beyond the target in direction (dy, dx) before a wall or the map's edge."""
        level = self.agent.current_level()
        y, x = int(target[1]), int(target[2])
        h, w = level.walkable.shape
        n = 0
        while n < 20:
            y, x = y + dy, x + dx
            if not (0 <= y < h and 0 <= x < w) or not level.walkable[y, x]:
                break
            n += 1
        return n

    @staticmethod
    def _immune(mon, name):
        """The target's kind takes nothing from a zap of wand type `name` (zap.c zhitm / bhitm): sleep resistance,
        fire/cold/shock resistance, the magic-resistant kinds against magic missile and striking ('Boing!'); death
        rays through RESIST_AWARE_ZAP's own test. An unseen 'I' resists nothing we know of."""
        from .combat import fight_heur
        res = int(getattr(mon, 'mresists', 0) or 0)
        mname = getattr(mon, 'mname', '')
        if name == 'sleep':
            return bool(res & MR_SLEEP)
        if name in fight_heur._RESIST_MR:
            return bool(res & fight_heur._RESIST_MR[name])
        if name in ('striking', 'magic missile'):
            return mname in fight_heur._RESIST_MAGM
        return False

    # ------------------------------------------------------------------ the plan

    def _candidates(self, adjacent, why, loss):
        agent = self.agent
        dive = self.dive
        bl = agent.blstats
        critical = why == 'critical'
        stalker = any(getattr(m[3], 'mflags2', 0) & MON.M2_STALK for m in adjacent)
        # 1. the up staircase under us
        if not stalker and self._ups_here():
            yield ('climb', None, 'on the up stairs')
        # 2-3. teleport ourselves (not with shop goods in the pack)
        if self._teleport_ok() and not self._unpaid():
            scroll = self._tele_scroll()
            if scroll is not None:
                yield ('read', scroll, 'known scroll of teleportation')
            wand, _ = self._wand(('teleportation',))
            if wand is not None:
                yield ('zapself', wand, 'known wand of teleportation at ourselves')
        # 4. a hole
        if not stalker and self._diggable():
            wand = dive.digging_wand()
            # WAND_RESERVE (#441): the kept wand of digging is spent here only when dive_logic would spend it too
            if wand is not None and wand in agent.inventory.items and dive._wand_escape(wand) is not None and \
                    not dive._wand_reserved():
                yield ('zapdown', wand, 'known wand of digging')
        # 5. heal
        potion = self._heal_potion(critical)
        if potion is not None:
            yield ('quaff', potion, 'known healing potion')
        # 6. at the strongest attacker next to us (never in Minetown or with a peaceful on the line)
        if not adjacent:
            return
        from .combat import fight_heur
        if fight_heur.missiles_risk_the_watch(agent):
            return
        if jf_config.KNOWN_ITEMS_TARGET:
            # the attacker that hurts most: monstr difficulty first; on Elbereth the one that ignores it
            # (makemon.c mstrength, monmove.c onscary; https://nethackwiki.com/wiki/Difficulty)
            on_elb = self._on_elbereth()
            target = max(adjacent, key=lambda m: (on_elb and dive._melee_ignores_elbereth(m[3]),
                                                  getattr(m[3], 'difficulty', 0), getattr(m[3], 'mlevel', 0)))
        else:
            target = max(adjacent, key=lambda m: getattr(m[3], 'mlevel', 0))
        if self._on_elbereth() and not dive._melee_ignores_elbereth(target[3]):
            return   # a zap at a monster our Elbereth scares deletes the engraving (mon.c setmangry)
        pos = (int(bl.y), int(bl.x))
        dy, dx = int(target[1]) - pos[0], int(target[2]) - pos[1]
        dy, dx = (dy > 0) - (dy < 0), (dx > 0) - (dx < 0)
        if self._line_hits_peaceful(dy, dx):
            return
        direction = agent.calc_direction(bl.y, bl.x, int(target[1]), int(target[2]))
        # a ray (sleep, fire, lightning, magic missile) with a wall close behind an adjacent target comes back
        # through us (zap.c buzz: range rn1(7,7), -2 per monster) -- only with room for it to die out
        safe_run = self._free_run_behind(target, dy, dx) >= jf_config.KNOWN_ITEMS_RAY_RUN
        name = getattr(target[3], 'mname', '?')
        mon = target[3]
        wand, wname = self._wand(('sleep',))
        if wand is not None and self._immune(mon, 'sleep'):
            wand = None
        if wand is None and critical and not self._immune(mon, 'sleep'):
            wand, wname = self._sleep_or_death(), 'sleep or death'
        if wand is not None and safe_run:
            yield ('zap', (wand, direction, target), f'known {wname} at the {name}')
        wand, _ = self._wand(('striking',))
        if wand is not None and not self._immune(mon, 'striking'):
            yield ('zap', (wand, direction, target), f'known striking at the {name}')
        wand, _ = self._wand(('cold',))
        if wand is not None and not dive.cold_reserved(wand) and not self._immune(mon, 'cold') and \
                (safe_run or agent.character.role == Character.VALKYRIE):
            yield ('zap', (wand, direction, target), f'known cold at the {name}')
        wand, _ = self._wand(('fire',))
        if wand is not None and safe_run and not self._immune(mon, 'fire'):
            yield ('zap', (wand, direction, target), f'known fire at the {name}')
        if safe_run:
            for wname in ('lightning', 'magic missile'):
                wand, _ = self._wand((wname,))
                if wand is not None and not self._immune(mon, wname):
                    yield ('zap', (wand, direction, target), f'known {wname} at the {name}')
                    break

    @staticmethod
    def _block_key(plan):
        kind, arg, _ = plan
        item = arg[0] if isinstance(arg, tuple) and arg and hasattr(arg[0], 'glyphs') else arg
        return (kind, item.glyphs[0] if hasattr(item, 'glyphs') else None)

    def _plan(self):
        """(kind, arg, why, danger) or None. Side-effect free: it runs as the preempt condition on every step."""
        if not jf_config.KNOWN_ITEMS or not self._in_scope():
            return None
        danger = self._danger()
        if danger is None or self._prayer_first() or self._minotaur_fight():
            return None
        turn = self.agent.blstats.time
        for plan in self._candidates(*danger):
            if self._blocked.get(self._block_key(plan), -1) < turn:
                return plan + (danger,)
        return None

    # ------------------------------------------------------------------ acting

    def _act(self, plan):
        agent = self.agent
        dive = self.dive
        kind, arg, why, (adjacent, trigger, loss) = plan
        bkey = self._block_key(plan[:3])
        t, n = self._attempts.get(bkey, (None, 0))
        n = n + 1 if t == agent.blstats.time else 1
        self._attempts[bkey] = (agent.blstats.time, n)
        if n >= 3:
            # the same action a third time within one game turn: it passes no time (refused) -- no loop on it
            self._blocked[bkey] = agent.blstats.time + 3
            agent.log(f'KNOWN_ITEMS {bkey} refused 3 times at T{agent.blstats.time}: blocked for 3 turns')
        bl = agent.blstats
        key = agent.current_level().key()
        near = [getattr(m[3], 'mname', '?') for m in adjacent[:4]]
        self.uses += 1
        agent.log(f'KNOWN_ITEMS {kind} ({why}): {trigger}, hp {bl.hitpoints}/{bl.max_hitpoints}, lost {loss} in '
                  f'{jf_config.KNOWN_ITEMS_BURST_TURNS} turns, next to us {near}, depth {bl.depth} (use {self.uses})')
        if kind == 'climb':
            agent.move('<')
            return
        if kind == 'read':
            from . import power_route
            power_route._read(agent, arg, f'KNOWN_ITEMS: {why}')
            if _NOTELEPORT in (agent.message or ''):
                self._noteleport.add(key)
            return
        if kind == 'zapself':
            agent.zap(arg, '.')
            agent.log(f'KNOWN_ITEMS zap -> {(agent.message or "")[:160]!r}')
            if _NOTELEPORT in (agent.message or ''):
                self._noteleport.add(key)
            agent.inventory.items.update(force=True)
            return
        if kind == 'zapdown':
            dive._escape_act(('zap', arg))
            return
        if kind == 'quaff':
            agent.inventory.quaff(arg)
            agent.log(f'KNOWN_ITEMS quaff -> {(agent.message or "")[:160]!r}')
            return
        if kind == 'zap':
            wand, direction, m = arg
            agent.zap(wand, direction)
            msg = agent.message or ''
            agent.log(f'KNOWN_ITEMS zap -> {msg[:160]!r}')
            if 'Nothing happens' in msg or 'You wrest' in msg:
                agent.inventory.empty_wands.add(wand.text)
            agent.inventory.items.update(force=True)
            return
        raise ValueError(kind)

    def strategy(self):
        def f():
            if not jf_config.KNOWN_ITEMS:
                yield False
                return
            plan = self._plan()
            if plan is None:
                yield False
                return
            yield True
            self._act(plan)

        return Strategy(f)

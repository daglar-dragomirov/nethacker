"""Wizard combat-only rescue on intact Evidence engine.

Known wand/spell risk policy from open69f6, with conditional shot attribution.
Never remove a hostile from threat because of a hit; leave existing ordinary
combat and minotaur escapes in charge after an item action. No sleep-melee lane.
"""
import math
import re
import nle.nethack as nh
from . import castle_power, jf_config, power, utils
from .glyph import G, Hunger
from . import wizard_rays
from .wizard_rays import DIRS, _cheb, charges, ray_outcomes, threat
from .combat.monster_utils import WEAK_MONSTERS
from .combat_hit_evidence import CombatHitEvidence

RAYS = ('sleep', 'death', 'fire', 'cold', 'lightning', 'magic missile')
BEAMS = ('teleportation', 'striking')
DECISIVE = ('sleep', 'death', 'teleportation')
FIGHT_WANDS = DECISIVE + ('fire', 'cold', 'lightning', 'magic missile', 'striking')
DICE = {'fire': (6, 6), 'cold': (6, 6), 'lightning': (6, 6), 'magic missile': (2, 6), 'striking': (2, 12)}
BEAM_RANGES = tuple(range(6, 14))
DAMAGE_PARTIAL = 0.25
SPELL_SLEEP = 'sleep'
_PREF = {'spell': 0, 'decisive': 1, 'damage': 2}

def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def p_kill(mon, kind):
    """P(one hit of `kind` -- fire/cold/lightning/magic missile/striking -- kills monster kind `mon`): its HP is
    mlevel d8 (makemon.c; 1d4 at level 0), the damage nd d sides (zap.c zhitm: 6d6 for a wand's fire/cold/lightning,
    2d6 magic missile; bhitm: striking 2d12, hitting when rnd(20) < 10 + its AC)."""
    lvl = max(0, int(getattr(mon, 'mlevel', 0) or 0))
    hp_m, hp_v = (2.5, 1.25) if lvl == 0 else (4.5 * lvl, 5.25 * lvl)
    n, s = DICE[kind]
    d_m, d_v = n * (s + 1) / 2.0, n * (s * s - 1) / 12.0
    p = 1.0 - _phi((hp_m - d_m - 0.5) / math.sqrt(hp_v + d_v))
    if kind == 'striking':
        ac = int(getattr(mon, 'ac', 5) if getattr(mon, 'ac', None) is not None else 5)
        p *= min(1.0, max(0.0, (9 + ac) / 20.0))
    return p

def effect(mon, kind):
    """The fraction of monster `mon`'s threat one hit of `kind` removes (0 when it resists)."""
    base = castle_power.zap_effect(mon, kind) if kind in castle_power._ZAP_GOOD else 1.0
    if base <= 0:
        return 0.0
    if kind in DECISIVE:
        return base
    pk = p_kill(mon, kind)
    return base * (pk + DAMAGE_PARTIAL * (1 - pk))

def beam_outcomes(zap_pos, hero, d, mons, ranges=BEAM_RANGES):
    """zap.c bhit for an IMMEDIATE wand: from `hero` in direction d, range 6..13, -1 a square, -3 for every creature
    it reaches, stopping at the first square it can't pass. {pos: P(the beam reaches the creature there)}."""
    h, w = len(zap_pos), len(zap_pos[0])
    out = {}
    for r in ranges:
        y, x = hero
        rng = r
        while rng > 0:
            rng -= 1
            y, x = y + d[0], x + d[1]
            if not (0 <= y < h and 0 <= x < w) or not zap_pos[y][x]:
                break
            if (y, x) in mons:
                out[(y, x)] = out.get((y, x), 0.0) + 1.0 / len(ranges)
                rng -= 3
    return out

def _wand_name(item):
    obj = getattr(item, 'object', None)
    for name in FIGHT_WANDS + ('speed monster',):
        if obj is not None and obj == castle_power._W.get(name):
            return name
    return None

class WizardCombatGuard:
    def __init__(self,dive,mino):
        self.dive=dive
        self.agent=dive.agent
        self.mino=mino
        self.zaps=0
        self._tried={}
        self._hit_evidence={}
        self._hit_hp=None

    def _observe_hits(self):
        agent=self.agent
        key=agent.current_level().key()
        hp=(key,int(agent.blstats.hitpoints))
        lost_hp=self._hit_hp is not None and self._hit_hp[0]==key and hp[1]<self._hit_hp[1]
        self._hit_hp=hp
        visible={}
        for m in agent.get_visible_monsters():
            visible.setdefault(getattr(m[3],'mname','unknown'),set()).add((int(m[1]),int(m[2])))
        reliable=not getattr(agent.character.prop,'hallu',False) and not getattr(agent,'_terrain_view',False)
        for name,evidence in self._hit_evidence.items():
            evidence.observe(level=key,turn=int(agent.blstats.time),stamp=agent.step_count,
                message_stamp=getattr(agent,'_mino_message_stamp',agent.step_count),
                visible=visible.get(name,set()),message=agent.message or '',lost_hp=lost_hp,reliable=reliable)
        return visible

    def _recent_hit(self,monster):
        name=getattr(monster[3],'mname','unknown')
        evidence=self._hit_evidence.get(name)
        return evidence is not None and evidence.classify((int(monster[1]),int(monster[2])),
            level=self.agent.current_level().key(),turn=int(self.agent.blstats.time))=='recent_attributed_hit'

    def _usable(self):
        agent = self.agent
        ch = agent.character
        # blind / hallucinating: the monsters' names are unknown; confused or stunned: confdir() may turn the ray
        if ch.prop.blind or ch.prop.polymorph or \
                any(getattr(ch.prop, p, False) for p in ('stoned', 'hallu', 'confusion', 'stun')):
            return False
        try:
            cond = int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION])
        except Exception:  # noqa: BLE001
            cond = 0
        if cond & (nh.BL_MASK_STONE | nh.BL_MASK_SLIME | nh.BL_MASK_STRNGL | nh.BL_MASK_FOODPOIS | nh.BL_MASK_TERMILL):
            return False   # emergency_strategy's business (lizard, prayer)
        if agent.blstats.carrying_capacity >= 4:   # dozap/dodrink: check_capacity refuses when Overtaxed
            return False
        from .glyph import G
        from . import utils
        if utils.any_in(agent.glyphs, G.SWALLOW):
            return False
        return True

    def _hostiles(self):
        """Awake, non-trivial hostiles in view: [(monster tuple, distance)]."""
        agent = self.agent
        pos = (int(agent.blstats.y), int(agent.blstats.x))
        out = []
        on_elb = (agent.inventory.engraving_below_me or '').lower() == 'elbereth'
        for m in agent.get_visible_monsters():
            name = getattr(m[3], 'mname', 'unknown')
            if name in WEAK_MONSTERS:
                continue
            if on_elb and not self.dive._melee_ignores_elbereth(m[3]):
                continue
            d = _cheb((m[1], m[2]), pos)
            if d <= 7:
                out.append((m, d))
        return out

    def _zap_pos(self):
        return self.agent.current_level().walkable

    def _creatures(self):
        """Every creature on the map as {(y, x): kind}: 'hostile' (with its tuple), 'pet', 'peaceful'."""
        agent = self.agent
        from .glyph import G
        from . import utils
        out = {}
        for m in agent.get_visible_monsters():
            out[(int(m[1]), int(m[2]))] = ('hostile', m)
        pets = utils.isin(agent.glyphs, G.PETS)
        for y, x in zip(*pets.nonzero()):
            out[(int(y), int(x))] = ('pet', None)
        mons = utils.isin(agent.glyphs, G.MONS)
        me = (int(agent.blstats.y), int(agent.blstats.x))
        for y, x in zip(*mons.nonzero()):
            if (int(y), int(x)) not in out and (int(y), int(x)) != me:
                out[(int(y), int(x))] = ('peaceful', None)
        return out

    def _safe(self, planner):
        """A planner's result; an unexpected error in the (pure) planning is logged once per turn and means no plan."""
        try:
            return planner()
        except Exception as e:  # noqa: BLE001
            agent = self.agent
            if getattr(self, '_err_turn', None) != agent.blstats.time:
                self._err_turn = agent.blstats.time
                agent.log(f'WIZ_COMBAT {planner.__name__} error: {type(e).__name__}: {e}')
            return None

    def _blocked(self, key):
        """The same action twice in one game turn: it was refused (no time passed) -- skip it for this turn."""
        now = self.agent.blstats.time
        t, n = self._tried.get(key, (None, 0))
        n = n + 1 if t == now else 1
        self._tried[key] = (now, n)
        return n > 2

    def _role_ok(self):
        roles = jf_config.WIZ_KIT_ROLES
        if roles is None:
            return True
        from .item.ring_amulet_logic import _role_in
        try:
            return _role_in(self.agent, roles)
        except Exception:  # noqa: BLE001
            return False

    def _is_monk(self):
        from .character import Character
        return getattr(self.agent.character, 'role', None) == Character.MONK

    def _fight_lane(self):
        """The fight lane (fight_plan) acts for us: WIZ_WAND_FIGHT for the WIZ_KIT_ROLES, or MON_SLEEP_FIGHT for a Monk
        (its starting sleep spell, a third of Monks, and the attack wands it finds)."""
        if jf_config.WIZ_WAND_FIGHT and self._role_ok():
            return True
        return bool(jf_config.MON_SLEEP_FIGHT) and self._is_monk()

    def _fight_items(self):
        """[(kind, name, item or None)] -- kind 'spell' / 'decisive' / 'damage'; item None for the sleep spell."""
        agent = self.agent
        out = []
        ch = agent.character
        spells = getattr(ch, 'known_spells', {}) or {}
        if jf_config.WIZ_SLEEP_SPELL and SPELL_SLEEP in spells and agent.blstats.energy >= 5 and \
                getattr(ch, 'spell_fail_chance', {}).get(SPELL_SLEEP, 1) <= 0.3 and \
                agent.blstats.hunger_state < Hunger.WEAK and agent.blstats.carrying_capacity < 2:
            from .combat import fight_heur
            if not fight_heur._fb_cannot_cast(agent):
                out.append(('spell', SPELL_SLEEP, None))
        for it in agent.inventory.items:
            if not (it.is_wand() and it.is_unambiguous()) or power._empty(agent, it) or it.comment == 'EMPT':
                continue
            name = _wand_name(it)
            if name in FIGHT_WANDS:
                out.append(('decisive' if name in DECISIVE else 'damage', name, it))
        return out

    def _mr_worn(self):
        return any(getattr(i, 'equipped', False) and 'magic resistance' in (getattr(i, 'text', '') or '')
                   for i in self.agent.inventory.items)

    def _sleep_resistant(self):
        from .character import Character
        ch = self.agent.character
        if getattr(ch, 'race', None) == Character.ELF and self.agent.blstats.experience_level >= 4:
            return True   # attrib.c elf_abil: sleep resistance at XL 4
        if jf_config.MON_SLEEP_FIGHT and getattr(ch, 'role', None) == Character.MONK:
            return True   # attrib.c mon_abil: sleep resistance at XL 1
        return False

    def _self_harmless(self, name):
        if name in ('magic missile', 'death'):
            return self._mr_worn()   # zap.c zhitu: Antimagic -> 'the missiles bounce off' / 'You aren't affected'
        if name == 'sleep':
            return self._sleep_resistant()
        return False

    def _line_gain(self, name, kind, d, hero, creatures, zap_pos, weight):
        """(gain, hits [(m, p)], self_p) of `name` along direction d, or None when the line is refused."""
        if name in RAYS:
            harmless = self._self_harmless(name)
            # a ray that can't hurt us flies on through our square (buzz: zap_hit(u.uac) then zhitu; the hea_kit model
            # stops crediting hits after the ray reaches us, so it runs with p_self = 0 here)
            self_p, hit_p = ray_outcomes(zap_pos, hero, d, {p: k for p, k in creatures.items()},
                                         p_self=0.0 if harmless else wizard_rays.P_SELF_HIT)
            if self_p > jf_config.WIZ_WAND_SELF_P and not harmless:
                return None
        else:
            self_p, hit_p = 0.0, beam_outcomes(zap_pos, hero, d, creatures)
        if any(creatures[p][0] in ('peaceful', 'pet') and q > 0.01 for p, q in hit_p.items()):
            return None
        gain = 0.0
        hits = []
        for p, q in hit_p.items():
            k, m = creatures[p]
            if k != 'hostile':
                continue
            if name == 'sleep' and self._recent_hit(m):
                continue  # avoid re-spending sleep on a recent attributed hit; it remains in the threat model
            eff = effect(m[3], name)
            gain += q * eff * weight.get(p, 0.0)
            if eff > 0:
                hits.append((m, q))
        return gain, hits, self_p

    def fight_plan(self):
        """('zap' | 'cast', item or None, name, (dy, dx), why, hits) or None. Side-effect free apart from forgetting
        stale sleepers."""
        if not self._fight_lane() or not self._usable():
            return None
        agent = self.agent
        from .combat import fight_heur
        if fight_heur.missiles_risk_the_watch(agent) or utils.any_in(agent.glyphs, G.SHOPKEEPER):
            return None
        items = self._fight_items()
        if not items:
            return None
        self._observe_hits()
        hostiles = self._hostiles()
        if not hostiles:
            return None
        bl = agent.blstats
        names = [(getattr(m[3], 'mname', 'unknown'), d) for m, d in hostiles]
        p_die, each = threat(names, bl.hitpoints, bl.armor_class, bl.depth, bl.experience_level,
                             jf_config.WIZ_WAND_TURNS)
        if p_die < jf_config.WIZ_WAND_PDIE:
            return None
        if self.mino._prayer_first():
            return None    # emergency_strategy (below) prays first: 3 invulnerable turns and full HP
        bolt = fight_heur._fb_castable(agent)
        on_elb = (agent.inventory.engraving_below_me or '').lower() == 'elbereth'
        hero = (int(bl.y), int(bl.x))
        creatures = self._creatures()
        zap_pos = self._zap_pos()
        weight = {(int(m[1]), int(m[2])): w for (m, _), w in zip(hostiles, each)}
        total = sum(each)
        best = None
        for kind, name, it in items:
            if kind == 'damage' and bolt and p_die < jf_config.WIZ_WAND_PDIE_BOLT:
                continue
            if it is not None and not self.dive.diving:
                n = charges(it)
                if n is not None and n <= jf_config.WIZ_WAND_RESERVE and p_die < jf_config.WIZ_WAND_PDIE_LAST:
                    continue
            if on_elb and name in BEAMS:
                continue
            for d in DIRS:
                if not any(self._on_line_r(hero, pos, d, jf_config.WIZ_WAND_RANGE) for pos in weight):
                    continue
                r = self._line_gain(name, kind, d, hero, creatures, zap_pos, weight)
                if r is None:
                    continue
                gain, hits, self_p = r
                if gain <= 0 or gain < jf_config.WIZ_WAND_MIN_SHARE * total:
                    continue
                key = (gain, -_PREF[kind])
                if best is None or key[0] > best[0][0] * 1.1 or \
                        (key[0] >= best[0][0] * 0.9 and key[1] > best[0][1]):
                    best = (key, kind, name, it, d, hits, self_p)
        if best is None:
            return None
        (gain, _), kind, name, it, d, hits, self_p = best
        why = f'P(death in {jf_config.WIZ_WAND_TURNS} turns)={p_die:.2f}, gain {gain:.1f}/{total:.1f}, self {self_p:.3f}'
        return ('cast' if kind == 'spell' else 'zap', it, name, d, why, hits)

    @staticmethod
    def _on_line_r(hero, pos, d, reach):
        dy, dx = pos[0] - hero[0], pos[1] - hero[1]
        k = max(abs(dy), abs(dx))
        if k == 0 or k > reach:
            return False
        return (dy, dx) == (d[0] * k, d[1] * k)

    def _act_fight(self, plan):
        verb, it, name, d, why, hits = plan
        agent = self.agent
        bl = agent.blstats
        self.zaps += 1
        names = [getattr(m[3], 'mname', '?') for m, _ in hits]
        what = f'the {name} spell' if it is None else repr(it.text)
        agent.log(f'WIZ_COMBAT {verb} {what} {d} ({why}) at {names}, hp {bl.hitpoints}/{bl.max_hitpoints} '
                  f'pw {bl.energy} (use {self.zaps})')
        armed=[]
        if name=='sleep':
            visible=self._observe_hits()
            for m,_ in hits:
                mname=getattr(m[3],'mname','unknown')
                coords=visible.get(mname,set())
                target=(int(m[1]),int(m[2]))
                if len(coords)!=1 or target not in coords:
                    continue
                evidence=self._hit_evidence.setdefault(mname,CombatHitEvidence(mname))
                evidence.observe(level=agent.current_level().key(),turn=int(bl.time),stamp=agent.step_count,
                    message_stamp=getattr(agent,'_mino_message_stamp',agent.step_count),visible=coords)
                evidence.arm(level=agent.current_level().key(),turn=int(bl.time),
                    origin=(int(bl.y),int(bl.x)),target=target,visible=coords)
                armed.append(evidence)
        try:
            if verb=='cast':
                agent.cast(SPELL_SLEEP,d)
            else:
                direction=agent.calc_direction(bl.y,bl.x,bl.y+d[0],bl.x+d[1])
                agent.zap(it,direction)
            self._observe_hits()
        finally:
            for evidence in armed:
                evidence.disarm()
        msg = agent.message or ''
        agent.log(f'WIZ_COMBAT {verb} -> {msg[:160]!r}')
        if it is not None and ('Nothing happens' in msg or 'You wrest' in msg):
            agent.inventory.empty_wands.add(it.text)
        agent.inventory.items.update(force=True)

    def strategy(self):
        from .strategy import Strategy
        def f():
            if not jf_config.WIZ_WAND_FIGHT or not self._role_ok():
                yield False
                return
            plan=self._safe(self.fight_plan)
            if plan is not None and not self._blocked((plan[0],plan[2],plan[3])):
                yield True
                self._act_fight(plan)
                return
            yield False
        return Strategy(f)

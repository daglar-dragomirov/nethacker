"""Elective Wizard equipment only; open69f6 lifecycle on intact Evidence core.
No donor combat, ray, sleeper, Ranger or route controller is imported.
"""
import re
import nle.nethack as nh
from . import castle_power, jf_config, power, utils
from .glyph import G, Hunger

def _cheb(a,b):
    return max(abs(a[0]-b[0]),abs(a[1]-b[1]))

def _wand_name(item):
    obj=getattr(item,'object',None)
    return 'speed monster' if obj is not None and obj==castle_power._W.get('speed monster') else None

def _buc_known_ok(item):
    """The game printed the item as uncursed or blessed (a starting item always shows its BUC)."""
    t = getattr(item, 'text', '') or ''
    return bool(re.search(r'\b(uncursed|blessed)\b', t)) and 'unpaid' not in t

class WizardEquipmentGuard:
    def __init__(self,dive,mino):
        self.agent=dive.agent
        self.dive=dive
        self.mino=mino
        self._tried={}
        self.speed_done=False
        self.boosts={}
        self.ring_tries={}
        self.regen_glyph=None

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

    def _safe(self, planner):
        """A planner's result; an unexpected error in the (pure) planning is logged once per turn and means no plan."""
        try:
            return planner()
        except Exception as e:  # noqa: BLE001
            agent = self.agent
            if getattr(self, '_err_turn', None) != agent.blstats.time:
                self._err_turn = agent.blstats.time
                agent.log(f'WIZ_EQUIPMENT {planner.__name__} error: {type(e).__name__}: {e}')
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

    def _calm(self, radius=6):
        """No hostile within `radius` (Chebyshev) and nothing hurt us this turn."""
        agent = self.agent
        pos = (int(agent.blstats.y), int(agent.blstats.x))
        return not any(_cheb((m[1], m[2]), pos) <= radius for m in agent.get_visible_monsters())

    def _in_shop_view(self):
        agent = self.agent
        try:
            if utils.any_in(agent.glyphs, G.SHOPKEEPER):
                return True
        except Exception:  # noqa: BLE001
            pass
        return any('unpaid' in (getattr(i, 'text', '') or '') for i in agent.inventory.items)

    def speed_plan(self):
        if not jf_config.WIZ_SPEED_SELF or self.speed_done or not self._role_ok() or not self._usable():
            return None
        if not self._calm() or self._in_shop_view():
            return None
        for it in self.agent.inventory.items:
            if it.is_wand() and it.is_unambiguous() and _wand_name(it) == 'speed monster' and \
                    not power._empty(self.agent, it) and it.comment != 'EMPT':
                return ('zapself', it)
        return None

    def boost_plan(self):
        if not jf_config.WIZ_KIT_BOOST or not self._role_ok() or not self._usable():
            return None
        agent = self.agent
        ch = agent.character
        if getattr(ch.prop, 'confusion', False) or getattr(ch.prop, 'stun', False) or getattr(ch.prop, 'hallu', False):
            return None
        if not self._calm() or self._in_shop_view():
            return None
        for it in agent.inventory.items:
            if not it.is_unambiguous() or not _buc_known_ok(it) or self.boosts.get(it.text, 0) >= 2:
                continue
            name = getattr(it.object, 'name', '')
            if it.category == nh.POTION_CLASS and name in jf_config.WIZ_BOOST_POTIONS:
                return ('quaff', it, name)
            if it.category == nh.SCROLL_CLASS and name == 'enchant armor':
                worn = [i for i in agent.inventory.items if i.is_armor() and i.equipped]
                if worn and all((i.modifier or 0) <= 3 for i in worn):
                    return ('read', it, name)
        return None

    def _ring_slots(self):
        return sum(1 for i in self.agent.inventory.items if i.category == nh.RING_CLASS and i.equipped)

    def ring_plan(self):
        """('puton' | 'remove', ring, why) or None."""
        if not jf_config.WIZ_RING_SAFE or not self._role_ok() or not self._usable():
            return None
        agent = self.agent
        from .item import ring_amulet_config as rcfg
        from .item.ring_amulet_logic import _safe_to_put_on, _puton_blocked
        bl = agent.blstats
        inv = agent.inventory
        now = bl.time
        weak = bl.hunger_state >= Hunger.WEAK
        rings = [i for i in inv.items if i.category == nh.RING_CLASS and i.is_unambiguous()
                 and 'unpaid' not in (getattr(i, 'text', '') or '')]

        def recent(it):
            return now - self.ring_tries.get(it.glyphs[0], -10 ** 9) < jf_config.WIZ_RING_RETRY

        # regeneration: off when healed or Weak (needs no calm: #remove is one action)
        regen = [i for i in rings if i.object.name == 'regeneration']
        worn_regen = next((i for i in regen if i.equipped and i.glyphs[0] == self.regen_glyph), None)
        if worn_regen is not None and (weak or bl.hitpoints >= jf_config.WIZ_REGEN_OFF * bl.max_hitpoints) and \
                not recent(worn_regen) and self._calm(1):
            return ('remove', worn_regen, 'regeneration: healed' if not weak else 'regeneration: Weak')
        if bl.depth >= rcfg.MAX_DEPTH:
            return None
        try:
            if int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION]) & nh.BL_MASK_LEV:
                return None
        except Exception:  # noqa: BLE001
            pass
        if weak:
            return None
        free = self._ring_slots() < 2
        if not free:
            return None
        if bl.hitpoints < jf_config.WIZ_REGEN_ON * bl.max_hitpoints and self._calm(1):
            it = next((i for i in regen if not i.equipped and _safe_to_put_on(inv, i) and not recent(i) and
                       not _puton_blocked(inv, i)), None)
            if it is not None:
                return ('puton', it, f'regeneration: hp {bl.hitpoints}/{bl.max_hitpoints}')
        if not self._calm():
            return None
        wanted = tuple(rcfg.ALWAYS_WEAR_RINGS) + tuple(jf_config.WIZ_RING_EXTRA or ())
        for name in wanted:
            it = next((i for i in rings if i.object.name == name and not i.equipped and _safe_to_put_on(inv, i)
                       and not recent(i) and not _puton_blocked(inv, i)
                       and i.glyphs[0] not in getattr(inv, '_known_stuck_ring_amulet_glyphs', set())), None)
            if it is not None:
                return ('puton', it, f'always-wear {name}')
        return None

    def _act_ring(self, plan):
        verb, it, why = plan
        agent = self.agent
        inv = agent.inventory
        self.ring_tries[it.glyphs[0]] = agent.blstats.time
        agent.log(f'WIZ_RING {verb} {it.text!r} ({why})')
        if verb == 'puton':
            ok = inv.put_on(it)
            from .item import ring_amulet_config as rcfg
            if ok and it.object.name not in rcfg.ALWAYS_WEAR_RINGS:
                # ours to take off: the module's hunger shedding (Hungry) would fight our put on every turn
                getattr(inv, '_module_worn', set()).discard(it.glyphs[0])
            if ok and it.object.name == 'regeneration':
                self.regen_glyph = it.glyphs[0]
        else:
            ok = inv.remove_ring_or_amulet(it)
            if ok:
                self.regen_glyph = None
        agent.log(f'WIZ_RING {verb} -> ok={ok} {(agent.message or "")[:100]!r}')

    def strategy(self):
        from .strategy import Strategy

        def f():
            if not (jf_config.WIZ_SPEED_SELF or jf_config.WIZ_KIT_BOOST or
                    jf_config.WIZ_RING_SAFE):
                yield False
                return
            agent = self.agent
            plan = self._safe(self.speed_plan)
            if plan is not None:
                yield True
                self.speed_done = True
                agent.log(f'WIZ_SPEED zapping {plan[1].text!r} at ourselves')
                agent.zap(plan[1], '.')
                agent.log(f'WIZ_SPEED -> {(agent.message or "")[:120]!r}')
                agent.inventory.items.update(force=True)
                return
            plan = self._safe(self.ring_plan)
            if plan is not None and not self._blocked(('ring', plan[0], plan[1].glyphs[0])):
                yield True
                self._act_ring(plan)
                return
            plan = self._safe(self.boost_plan)
            if plan is not None and not self._blocked(('boost', plan[1].text)):
                yield True
                verb, it, name = plan
                self.boosts[it.text] = self.boosts.get(it.text, 0) + 1
                agent.log(f'WIZ_BOOST {verb} {it.text!r}')
                if verb == 'quaff':
                    agent.inventory.quaff(it)
                else:
                    self.mino._read(it, f'WIZ_BOOST {name}')
                agent.log(f'WIZ_BOOST -> {(agent.message or "")[:120]!r}')
                agent.inventory.items.update(force=True)
                return
            yield False

        return Strategy(f)

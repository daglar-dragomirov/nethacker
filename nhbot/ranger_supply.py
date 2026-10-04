"""Experimental Ranger supply controller on intact Public12Evidence.

Recovery scope, radius6/cooldown300 and calm guards derive from open zarutskiysy
69f6da875ef24c95614a910b3444ad39112a0d8c MISSILE_RECOVER/RAN_AMMO_VIEW.
Known compatible ground ammo already works in the intact Evidence inventory.
This module adds a bounded calm dive visit, and no combat swap policy.
"""
import nle.nethack as nh
from .character import Character
from .glyph import G,Hunger
from .item import Item,flatten_items
from .level import Level
from .strategy import Strategy

DIST=6
COOLDOWN=300
LOW_AMMO=5

def safe_launchers(agent):
    return [i for i in flatten_items(agent.inventory.items)
            if i.shop_status!=Item.UNPAID and i.status in (Item.UNCURSED,Item.BLESSED)
            and i.is_launcher() and i.object.name!='sling']

def launcher_skill(agent):
    """Known carried launcher; retains a choice when its ammo is temporarily empty."""
    if agent.character.role!=Character.RANGER or agent.character.prop.polymorph:
        return None
    try:
        launchers=safe_launchers(agent)
        equipped=next((i for i in launchers if i.equipped),None)
        best,_=agent.inventory.get_best_ranged_set()
        chosen=equipped or (best if best in launchers else None) or next(iter(launchers),None)
        return None if chosen is None else abs(int(chosen.objs[0].sub))
    except Exception:
        return None

class RangerSupplyGuard:
    def __init__(self,dive):
        self.dive=dive;self.agent=dive.agent;self.done={};self.attempts={}
        self._ammo_glyph_cache={}

    def _calm(self):
        a=self.agent;c=a.character;b=a.blstats;l=a.current_level()
        if c.role!=Character.RANGER or not self.dive.diving or c.prop.polymorph:
            return False
        if c.prop.blind or any(getattr(c.prop,p,False) for p in ('stoned','hallu','confusion','stun')):
            return False
        cond=int(a.last_observation['blstats'][nh.NLE_BL_CONDITION])
        if cond&(nh.BL_MASK_STONE|nh.BL_MASK_SLIME|nh.BL_MASK_STRNGL|nh.BL_MASK_FOODPOIS|nh.BL_MASK_TERMILL):
            return False
        if b.hunger_state>=Hunger.WEAK or b.hitpoints<.5*b.max_hitpoints or b.carrying_capacity>0:
            return False
        if l.dungeon_number==Level.SOKOBAN or self.dive.levitating() or self.dive.on_medusa_level() or self.dive.castle.active():
            return False
        here=(int(b.y),int(b.x))
        if l.shop[here] or l.shop_interior[here] or a.glyphs[here] in G.SWALLOW:
            return False
        for y in range(a.glyphs.shape[0]):
            for x in range(a.glyphs.shape[1]):
                if a.glyphs[y,x] in G.SHOPKEEPER or a.glyphs[y,x] in G.SWALLOW:
                    return False
        return not any(max(abs(int(m[1])-b.y),abs(int(m[2])-b.x))<=7 for m in a.get_visible_monsters())

    def _launchers(self):
        items=list(flatten_items(self.agent.inventory.items))
        return [l for l in safe_launchers(self.agent)
                if sum(int(i.count) for i in items if i.shop_status!=Item.UNPAID and i.is_fired_projectile(l))<LOW_AMMO]

    def _glyphs(self,launchers):
        names=set()
        for l in launchers:
            names.update(('crossbow bolt',) if l.object.name=='crossbow' else ('arrow','elven arrow','orcish arrow','silver arrow','ya'))
        key=frozenset(names)
        if key not in self._ammo_glyph_cache:
            self._ammo_glyph_cache[key]=frozenset(g for g in G.NORMAL_OBJECTS
                if nh.objdescr.from_idx(nh.glyph_to_obj(g)).oc_name in names)
        return self._ammo_glyph_cache[key]

    def _items_here(self,launchers):
        return [i for i in (self.agent.inventory.items_below_me or [])
                if i.shop_status==Item.NOT_SHOP and any(i.is_fired_projectile(l) for l in launchers)]

    def plan(self):
        if not self._calm():return None
        launchers=self._launchers()
        if not launchers:return None
        a=self.agent;l=a.current_level();b=a.blstats;here=(int(b.y),int(b.x));key=l.key();now=int(b.time)
        if now-self.done.get((key,here),-10**9)>=COOLDOWN and self._items_here(launchers):return ('pickup',here)
        glyphs=self._glyphs(launchers);dis=a.bfs();choices=[]
        for y in range(a.glyphs.shape[0]):
            for x in range(a.glyphs.shape[1]):
                p=(y,x);d=int(dis[p])
                if not 0<d<=DIST or a.glyphs[p] not in glyphs or now-self.done.get((key,p),-10**9)<COOLDOWN:
                    continue
                path=a.path(*here,*p,dis=dis)
                if any(l.shop[q] or l.shop_interior[q] or a.glyphs[q] in G.TRAPS for q in path[1:]):
                    continue
                choices.append((d,y,x))
        if not choices:return None
        _,y,x=min(choices);return ('walk',(y,x))

    @Strategy.wrap
    def strategy(self):
        try:plan=self.plan()
        except Exception as ex:
            self.agent.log(f'RANGER_SUPPLY check: {type(ex).__name__}');plan=None
        if plan is None:
            yield False
            return
        yield True
        # Revalidate after the outer strategy scheduler yields to higher-priority guards.
        if self.plan()!=plan:return
        action,target=plan;a=self.agent;key=(a.current_level().key(),target)
        n=self.attempts.get(key,0)+1;self.attempts[key]=n
        if n>3*DIST:
            self.done[key]=int(a.blstats.time);self.attempts.pop(key,None);return
        before=(int(a.blstats.time),int(a.blstats.y),int(a.blstats.x))
        if action=='walk':
            a.go_to(*target,max_steps=1,callback=lambda:not self._calm())
        else:
            items=self._items_here(self._launchers())
            if items:a.inventory.pickup(items)
            self.done[key]=int(a.blstats.time);self.attempts.pop(key,None)
        after=(int(a.blstats.time),int(a.blstats.y),int(a.blstats.x))
        if before==after:
            self.done[key]=int(a.blstats.time);self.attempts.pop(key,None)

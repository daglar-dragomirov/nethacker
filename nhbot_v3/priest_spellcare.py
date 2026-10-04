"""Conservative Priest healing capability preservation on Public12Evidence.

Primary mechanic: NetHack3.6 spell.c percent_success penalizes heavy shields.
Protect only a currently usable known healing spell and an already worn light
shield, trading at most two AC. Never remove armor, predict spell failure, or
replace reflection. Skill preference concerns the same known healing capability.
"""
from .character import Character
from . import objects as O
from .item import Item

MAX_AC_LOSS=2

def known_healing(character,usable=False):
    if character.role!=Character.PRIEST or character.prop.polymorph:
        return False
    for name,limit in (('healing',.2),('extra healing',.15)):
        letter=getattr(character,'known_spells',{}).get(name)
        chance=getattr(character,'spell_fail_chance',{}).get(name)
        if not getattr(character,'_priest_spellcare_retention',{}).get(name,False):
            continue
        if not isinstance(letter,str) or len(letter)!=1:
            continue
        if not usable or (chance is not None and 0<=chance<=limit):
            return True
    return False

def healing_skill(character):
    return O.P_HEALING_SPELL if known_healing(character) else None

def preferred_shield(agent,proposed):
    """Pure selector hook; no game action or new tactical swap is performed."""
    if proposed is None or not known_healing(agent.character,usable=True):
        return proposed
    current=agent.inventory.items.off_hand
    if current is None or current is proposed:
        return proposed
    for item in (current,proposed):
        if not item.is_armor() or not item.is_unambiguous() or item.object.sub!=O.ARM_SHIELD:
            return proposed
        if item.shop_status!=Item.NOT_SHOP or item.status not in (Item.UNCURSED,Item.BLESSED):
            return proposed
        if item.object.name=='shield of reflection':
            return proposed
    if not current.equipped or current.object.wt>30 or proposed.object.wt<=30:
        return proposed
    loss=current.get_ac()-proposed.get_ac()
    if not 0<=loss<=MAX_AC_LOSS:
        return proposed
    return current

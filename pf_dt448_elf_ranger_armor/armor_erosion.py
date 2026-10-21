"""Bounded visible ordinary armor contribution, not full worn defense.

Derived for the completed SIGNED elf-Ranger strategy. Outside the supported
raw observation, preserve that strategy's Item.get_ac exactly.
"""
import re

_PREFIX = re.compile(
    r'(?P<article>a|an|the|[1-9][0-9]*) (?P<buc>uncursed|blessed) '
    r'(?:greased )?'
    r'(?:(?:(?P<first_degree>very|thoroughly) )?(?P<first>rusty|burnt) )?'
    r'(?:(?:(?P<second_degree>very|thoroughly) )?(?P<second>corroded|rotted) )?'
    r'(?P<proof>rustproof )?(?P<spe>[+-][0-9]+) (?P<name>.+)'
)
_DEGREES = {None: 1, 'very': 2, 'thoroughly': 3}


def ordinary_armor_erosion_penalty(item):
    from . import objects as O
    from .item.item import Item
    if not isinstance(item, Item) or not item.is_armor() or len(item.objs) != 1:
        return 0
    if item.status not in (Item.UNCURSED, Item.BLESSED):
        return 0
    if not isinstance(item.modifier, int) or isinstance(item.modifier, bool):
        return 0
    if item.naming or item.comment or item.dmg_bonus is not None or item.to_hit_bonus is not None:
        return 0
    obj = item.objs[0]
    if not isinstance(obj, O.Armor) or not any(obj is original for original in O.objects):
        return 0
    if not isinstance(obj.name, str) or not obj.name or obj.mgc != 0 or obj.power != 0:
        return 0
    base = -obj.ac
    if not isinstance(base, int) or isinstance(base, bool) or not 0 <= base <= 10:
        return 0
    material = obj.metal
    if not isinstance(material, int) or isinstance(material, bool):
        return 0
    if not (O.LIQUID < material <= O.WOOD or material in (O.IRON, O.COPPER, O.PLASTIC)):
        return 0
    raw = item.text
    if not isinstance(raw, str) or ' named ' in raw or ' called ' in raw:
        return 0
    observed = _PREFIX.fullmatch(raw)
    if observed is None or observed['name'] != obj.name:
        return 0
    if int(observed['spe']) != item.modifier:
        return 0
    status = Item.UNCURSED if observed['buc'] == 'uncursed' else Item.BLESSED
    if status != item.status or (observed['proof'] and material != O.IRON):
        return 0
    if observed['first'] and observed['first'] != ('rusty' if material == O.IRON else 'burnt'):
        return 0
    if observed['second'] and observed['second'] != ('corroded' if material in (O.IRON, O.COPPER) else 'rotted'):
        return 0
    first = _DEGREES[observed['first_degree']] if observed['first'] else 0
    second = _DEGREES[observed['second_degree']] if observed['second'] else 0
    return min(max(first, second), base)

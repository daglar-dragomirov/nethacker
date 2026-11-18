"""Observable ordinary armor component from pinned ARM_BONUS; not full defense.

Preserve the selected completed Valk engine outside the bounded raw observation.
"""
import re

_OBSERVED = re.compile(
    r'^(?:a|an|the|[0-9]+) (?P<buc>uncursed|blessed) '
    r'(?:greased )?'
    r'(?:(?:(?P<pdegree>very|thoroughly) )?(?P<primary>rusty|burnt) )?'
    r'(?:(?:(?P<sdegree>very|thoroughly) )?(?P<secondary>corroded|rotted) )?'
    r'(?P<proof>rustproof )?(?P<spe>[+-][0-9]+) (?P<name>.+)$'
)
_DEGREE = {None: 1, 'very': 2, 'thoroughly': 3}


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
    if not isinstance(obj, O.Armor) or obj not in O.objects:
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
    text = item.text
    if not isinstance(text, str) or ' named ' in text or ' called ' in text:
        return 0
    observed = _OBSERVED.fullmatch(text)
    if observed is None or observed['name'] != obj.name or int(observed['spe']) != item.modifier:
        return 0
    raw_status = Item.UNCURSED if observed['buc'] == 'uncursed' else Item.BLESSED
    if item.status != raw_status:
        return 0
    if observed['proof'] and material != O.IRON:
        return 0
    primary_word = 'rusty' if material == O.IRON else 'burnt'
    secondary_word = 'corroded' if material in (O.IRON, O.COPPER) else 'rotted'
    if observed['primary'] and observed['primary'] != primary_word:
        return 0
    if observed['secondary'] and observed['secondary'] != secondary_word:
        return 0
    primary = _DEGREE[observed['pdegree']] if observed['primary'] else 0
    secondary = _DEGREE[observed['sdegree']] if observed['secondary'] else 0
    return min(max(primary, secondary), base)

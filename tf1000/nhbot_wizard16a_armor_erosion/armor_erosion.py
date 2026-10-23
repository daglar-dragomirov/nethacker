"""Observed ordinary armor contribution, not complete defense/efficacy.

Exact ARM_BONUS caps greatest erosion at unenchanted armor protection.
The inherited object.ac is NEGATIVE protection; do not floor enchantment.
Preserve evaluated policy outside the visible ordinary guard.
"""
import re
from .weapon_erosion import observed_erosion

def ordinary_armor_erosion_penalty(item):
    erosion, poisoned = observed_erosion(getattr(item, 'text', None))
    if not erosion or poisoned or item.modifier is None:
        return 0
    if not re.match(r'^(?:a|an|the|[0-9]+)(?: empty)? (?:cursed|uncursed) ', getattr(item, 'text', '') or ''):
        return 0
    if len(item.objs) != 1 or getattr(item, 'naming', '') or item.dmg_bonus is not None or item.to_hit_bonus is not None:
        return 0
    obj = item.objs[0]
    # Ordinary nonmagical, non-property armor only. Named/artifact/magic and
    # nonstandard object-table contexts keep the exact evaluated parent.
    if getattr(item, 'status', 0) not in (1, 2) or getattr(obj, 'mgc', None) != 0 or getattr(obj, 'power', None) != 0:
        return 0
    base = -obj.ac
    if not isinstance(base, int) or not 0 <= base <= 10:
        return 0
    return min(erosion, base)

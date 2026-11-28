"""Observable ordinary eroded weapon component, not full hmon parity.

Use only the accepted inventory adjective prefix; never names/comments. Guard
unknown enchantment/observable beatitude, ambiguity, named/artifact bonuses, blessed, poison, silver.
Existing parent valuation is retained outside this explicit ordinary boundary.
"""
from collections import Counter
from functools import lru_cache
import re

_EFFECTS = r'(?:rustproof|poisoned|corroded|rusty|burnt|rotted|partly eaten|partly used|diluted|unlocked|locked|broken|moist|wet|greased)'
_PREFIX = re.compile(r'^(?:a|an|the|[0-9]+)(?: empty)?(?: (?:cursed|uncursed|blessed))?((?: (?:very |thoroughly )?' + _EFFECTS + r')*) ')

@lru_cache(maxsize=2048)
def observed_erosion(text):
    match = _PREFIX.match(text or '')
    if not match:
        return 0, False
    prefix = match.group(1)
    levels = [3 if degree == 'thoroughly ' else 2 if degree == 'very ' else 1
              for degree in re.findall(r'(?<![a-z])(?:(very |thoroughly ))?(?:rusty|corroded|burnt|rotted)(?![a-z])', prefix)]
    return max(levels, default=0), 'poisoned' in prefix

@lru_cache(maxsize=256)
def eroded_physical_expectation(expression, modifier, erosion):
    assert isinstance(modifier, int) and 1 <= erosion <= 3
    distribution = Counter({0: 1})
    for term in expression.split('+'):
        match = re.fullmatch(r'(\d*)d(\d+)', term)
        if match:
            count, sides = int(match[1] or 1), int(match[2])
            if not 1 <= count <= 3 or not 1 <= sides <= 20:
                raise ValueError('Unsupported physical weapon dice')
            for _ in range(count):
                next_distribution = Counter()
                for total, ways in distribution.items():
                    for roll in range(1, sides + 1):
                        next_distribution[total + roll] += ways
                distribution = next_distribution
        elif term.isdigit() and int(term) <= 20:
            distribution = Counter({total + int(term): ways for total, ways in distribution.items()})
        else:
            raise ValueError('Unsupported physical weapon damage expression')
    return sum((max(1, max(0, roll + modifier) - erosion) if roll + modifier > 0 else 0) * ways
               for roll, ways in distribution.items()) / sum(distribution.values())

def ordinary_eroded_item_component(item, weapon, large_monster):
    erosion, poisoned = observed_erosion(getattr(item, 'text', None))
    if not erosion or poisoned or item.modifier is None:
        return None
    if not re.match(r'^(?:a|an|the|[0-9]+)(?: empty)? (?:cursed|uncursed) ', getattr(item, 'text', '') or ''):
        return None
    if len(item.objs) != 1 or getattr(item, 'naming', '') or item.dmg_bonus is not None or item.to_hit_bonus is not None:
        return None
    # BLESSED is the source Item enum value3. Preserve target-specific blessed,
    # silver and artifact paths; their old approximations are not rebuilt here.
    if getattr(item, 'status', 0) == 3 or getattr(weapon, 'metal', None) == 14:
        return None
    expression = weapon.damage_large if large_monster else weapon.damage_small
    return eroded_physical_expectation(expression, item.modifier, erosion)

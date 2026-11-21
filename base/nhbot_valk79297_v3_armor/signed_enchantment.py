"""Known negative weapon enchantment: expected dmgval physical dice after spe/zero floor.

NLE1.3.0 weapon.c dmgval adds signed spe then clamps each physical roll to zero.
This is one component only. The caller retains its inherited artifact/material,
u.udaminc, strength/skill conditioning and final-combat-floor approximations.
"""
from collections import Counter
from functools import lru_cache
import re


@lru_cache(maxsize=256)
def negative_expected_damage(expression, modifier):
    assert modifier < 0
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
    return sum(max(0, roll + modifier) * ways for roll, ways in distribution.items()) / sum(distribution.values())

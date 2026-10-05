"""Observable ordinary projectile proxy for inventory choice; no target model."""
from collections import Counter
from functools import lru_cache
import re

THROWN = frozenset(('dagger', 'orcish dagger', 'elven dagger', 'silver dagger',
 'athame', 'worm tooth', 'knife', 'stiletto', 'scalpel', 'crysknife', 'dart', 'shuriken'))
BOWS = frozenset(('bow', 'elven bow', 'orcish bow', 'yumi'))
AMMO = frozenset(('arrow', 'elven arrow', 'orcish arrow', 'silver arrow', 'ya', 'crossbow bolt'))

@lru_cache(maxsize=128)
def damage_distribution(expression):
    distribution = Counter({0: 1})
    for term in expression.split('+'):
        match = re.fullmatch(r'(\d*)d(\d+)', term)
        if match:
            count, sides = int(match[1] or 1), int(match[2])
            if not 1 <= count <= 3 or not 1 <= sides <= 20:
                raise ValueError('Unsupported physical dice')
            for _ in range(count):
                next_distribution = Counter()
                for total, ways in distribution.items():
                    for roll in range(1, sides + 1):
                        next_distribution[total + roll] += ways
                distribution = next_distribution
        elif term.isdigit() and int(term) <= 20:
            distribution = Counter({total + int(term): ways for total, ways in distribution.items()})
        else:
            raise ValueError('Unsupported physical damage expression')
    return tuple(distribution.items())

def strength_damage(strength):
    return (-1 if strength < 6 else 0 if strength < 16 else 1 if strength < 18
            else 2 if strength == 18 else 3 if strength <= 93 else 4 if strength <= 108
            else 5 if strength < 118 else 6)

def ordinary(item, names):
    return (item.is_weapon() and item.is_unambiguous() and item.object.name in names
            and item.modifier is not None and not item.naming
            and item.dmg_bonus is None and item.to_hit_bonus is None
            and not any(word in (item.text or '').lower() for word in
                        ('rusty', 'corroded', 'burnt', 'rotted', 'poisoned', 'greased')))

def ordinary_projectile_bonus(character, launcher, ammo, large_monster):
    """Calibrate known physical terms, preserving unsupported parent contracts.

    Hit value omits target AC/size/distance/status, Luck and accuracy rings.
    Damage omits target-dependent special interactions and damage rings.
    Volley count, range, inventory admissibility and action priorities stay upstream.
    """
    if character.prop.polymorph or character.agent.inventory.items.off_hand is not None:
        return None
    if launcher is None:
        if not ordinary(ammo, THROWN) or not ammo.is_thrown_projectile():
            return None
    elif (not ordinary(launcher, BOWS | {'crossbow'}) or not ordinary(ammo, AMMO)
          or not ammo.is_fired_projectile(launcher)):
        return None
    skill_item = ammo if launcher is None else launcher
    skill_hit, skill_damage = character._get_weapon_skill_bonus(skill_item)
    if character.skill_levels[abs(skill_item.object.sub)] <= character.SKILL_LEVEL_UNSKILLED:
        skill_damage = -2
    bl = character.agent.blstats
    dex = bl.dexterity
    dex_hit = -3 if dex < 4 else -2 if dex < 6 else -1 if dex < 8 else dex - 14 if dex >= 14 else 0
    hit = -1 + bl.experience_level + dex_hit + ammo.object.hitbon + ammo.modifier + skill_hit
    racial_damage = 0
    wielded = launcher if launcher is not None else character.agent.inventory.items.main_hand
    if wielded is not None and wielded.is_unambiguous() and wielded.object.name in BOWS:
        gloves = character.agent.inventory.items.gloves
        if gloves is not None:
            if not gloves.is_unambiguous():
                return None
            hit -= {'gauntlets of power': 2, 'gauntlets of fumbling': 3}.get(gloves.object.name, 0)
    if launcher is None:
        # dothrow.c throwing_weapon: ordinary blade with PIERCE, or missile;
        # Athame/scalpel lack PIERCE; worm tooth has no attack-direction flag.
        hit += -2 if ammo.object.name in ('scalpel', 'athame', 'worm tooth') else 2
        strength = strength_damage(bl.strength)
    else:
        # Launcher enchantment contributes hit, never its physical dice/damage.
        hit += launcher.modifier
        strength = 0
        if launcher.object.name in BOWS:
            if character.race == character.ELF or character.role == character.SAMURAI:
                hit += 1
                if (character.race == character.ELF and launcher.object.name == 'elven bow'
                    or character.role == character.SAMURAI and launcher.object.name == 'yumi'):
                    hit += 1
            if (character.race == character.ELF and launcher.object.name == 'elven bow' and ammo.object.name == 'elven arrow'
                or character.role == character.SAMURAI and launcher.object.name == 'yumi' and ammo.object.name == 'ya'):
                racial_damage = 1
    expression = ammo.object.damage_large if large_monster else ammo.object.damage_small
    total = ways_total = 0
    for roll, ways in damage_distribution(expression):
        base = max(0, roll + ammo.modifier)
        before_bonus = base + racial_damage
        damage = before_bonus + (strength if before_bonus > 0 else 0) + (skill_damage if base > 1 else 0)
        total += ways * max(1, damage)
        ways_total += ways
    return hit, total / ways_total

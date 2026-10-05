"""Melee weapon-tools without changing the item's general category or actions."""
# objects.c WEPTOOL and weapon.c dmgval; grappling hook is not a projectile.
TOOL_DAMAGE = {'pick-axe': (6, 3), 'grappling hook': (2, 6), 'unicorn horn': (12, 12)}

def is_melee_tool(item):
    return (item is not None and item.is_unambiguous()
            and item.object.name in TOOL_DAMAGE)

def tool_can_be_selected(item, off_hand):
    return is_melee_tool(item) and not (item.object.bi and off_hand is not None)

def tool_melee_bonus(character, item, large_monster=False):
    """Observable physical proxy; no target AC or special-hit estimate."""
    if not is_melee_tool(item):
        raise ValueError('Not a supported weapon-tool')
    obj = item.object
    sides = TOOL_DAMAGE[obj.name][bool(large_monster)]
    skill_hit, skill_damage = character._get_weapon_skill_bonus(item)
    bl = character.agent.blstats
    enchantment = item.modifier
    roll = 1 + character._get_str_dex_to_hit_bonus() + bl.experience_level + skill_hit
    # The parent Item model adds an extra1 in get_weapon_bonus; tool support
    # uses actual hitval's enchantment plus the existing WEPTOOL hitbon table.
    roll += obj.hitbon + (enchantment or 0)
    safe = (enchantment is not None and not item.naming
            and item.dmg_bonus is None and item.to_hit_bonus is None
            and not character.prop.polymorph
            and character.agent.inventory.items.off_hand is None
            and not any(w in (item.text or '').lower() for w in
                        ('rusty', 'corroded', 'burnt', 'rotted', 'poisoned')))
    if not safe:
        # The old ordinary proxy, extended to this explicit tool table, lets
        # retention inspect unknown/eroded tools without asserting Item.is_weapon.
        hit = roll + 1 + (item.to_hit_bonus or 0)
        damage = (sides + 1) / 2 + max(0, enchantment or 0)
        return hit, max(0, damage + skill_damage + (item.dmg_bonus or 0))
    if character.skill_levels[abs(obj.sub)] <= character.SKILL_LEVEL_UNSKILLED:
        skill_damage = -2
    roll += bl.experience_level < 3
    if bl.carrying_capacity:
        roll -= 2 * bl.carrying_capacity - 1
    strength = bl.strength
    dbon = (-1 if strength < 6 else 0 if strength < 16 else 1 if strength < 18
            else 2 if strength == 18 else 3 if strength <= 93 else 4 if strength <= 108
            else 5 if strength < 118 else 6)
    damage = 0
    for die in range(1, sides + 1):
        base = max(0, die + enchantment)
        damage += max(1, base + (dbon if base > 0 else 0)
                      + (skill_damage if base > 1 else 0))
    return roll, damage / sides

"""Conservative observable volley budget for ordinary projectile valuation."""
def conservative_volley(character, launcher, ammo):
    """Expected capped count under NetHack's weak-multishot branch.

    Fumbling is not fully observable. Always assume weakmultishot, omitting
    the skilled and racial bonuses; role and expert bonuses still apply.
    This is a lower volley budget for inventory comparison, not target damage.
    The actual fire command is unchanged and imposes no numeric shot limit.
    """
    count = ammo.count
    if not isinstance(count, int) or count < 1:
        return 1.0
    if count == 1 or character.prop.confusion or character.prop.stun:
        return 1.0
    sub = ammo.object.sub
    level = character.skill_levels[abs(sub)]
    maximum = 1 + (level == character.SKILL_LEVEL_EXPERT)
    # dothrow.c role bonuses are independent of weakmultishot.
    if character.role == character.RANGER and sub != 1:  # P_DAGGER
        maximum += 1
    elif character.role == character.ROGUE and sub == 1:
        maximum += 1
    elif character.role == character.MONK and sub == -25:  # -P_SHURIKEN
        maximum += 1
    elif character.role == character.CAVEMAN and sub in (18, -22):  # P_SPEAR/-P_SLING
        maximum += 1
    elif (character.role == character.SAMURAI and launcher is not None
          and launcher.object.name == 'yumi' and ammo.object.name == 'ya'):
        maximum += 1
    if (launcher is not None and launcher.object.name == 'crossbow'
        and character.agent.blstats.strength_percentage < (16 if character.race == character.GNOME else 18)):
        return sum(sum(min(count, shots) for shots in range(1, draw + 1)) / draw
                   for draw in range(1, maximum + 1)) / maximum
    return sum(min(count, shots) for shots in range(1, maximum + 1)) / maximum

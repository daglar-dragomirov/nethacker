from collections import defaultdict
from itertools import product

import numpy as np
from scipy import signal

from ..glyph import G, MON
from .. import jf_config, utils
from .. import objects as O
from ..item import Item
from ..utils import adjacent
from .monster_utils import is_monster_faster, is_dangerous_monster, \
    ONLY_RANGED_SLOW_MONSTERS, EXPLODING_MONSTERS, WEAK_MONSTERS, consider_melee_only_ranged_if_hp_full
from .movement_priority import draw_monster_priority_positive, draw_monster_priority_negative
from .utils import wielding_ranged_weapon, line_dis_from, inside


def spore_blast_hits_friend(agent, y, x):
    """A gas spore killed at (y, x) explodes over its 3x3 square: a pet or peaceful there gets hurt and
    the hero gets the blame (a shopkeeper next to a spore turned hostile and killed an XL8 Valkyrie)."""
    sl = np.s_[max(y - 1, 0):y + 2, max(x - 1, 0):x + 2]
    if agent.monster_tracker.peaceful_monster_mask[sl].any() or utils.any_in(agent.glyphs[sl], G.PETS):
        return True
    if jf_config.SPORE_SAFE and _spore_blast_hits_people(agent, y, x):
        return True
    # a pet seen here lately but out of view now may be right behind the spore: a thrown dagger's blast
    # killed an unseen kitten ('You kill it!', 'rumble of distant thunder': -15 alignment on a Valkyrie's
    # record that starts at 0, so the first grind prayer failed at T1364)
    seen = agent.global_logic.dive.pet_seen.get(agent.current_level().key())
    return seen is not None and agent.blstats.time - seen < 100 and not utils.any_in(agent.glyphs, G.PETS)


def _spore_blast_hits_people(agent, y, x):
    """SPORE_SAFE: the blast also counts as our attack on whoever we don't know to be peaceful yet: any @ in
    the 3x3 (killing a watchman/shopkeeper/priest angered by it is murder even when he is hostile: Luck -2,
    telepathy lost), and anything at all on the Minetown level (base3-public s13: 'You kill the gas spore!  The
    watch captain is caught in the gas spore's explosion! ... You murderer!', prayers held 1200 turns)."""
    y0, x0 = agent.blstats.y, agent.blstats.x
    gl = agent.global_logic
    minetown = gl.minetown_level is not None and agent.current_level().key() == gl.minetown_level
    for yy in range(max(y - 1, 0), min(y + 2, agent.glyphs.shape[0])):
        for xx in range(max(x - 1, 0), min(x + 2, agent.glyphs.shape[1])):
            if (yy, xx) in ((y, x), (y0, x0)):
                continue
            g = agent.glyphs[yy, xx]
            if not MON.is_monster(g):
                continue
            if minetown:
                return True
            mlet = MON.permonst(g).mlet
            if (ord(mlet) if isinstance(mlet, str) else mlet) == MON.S_HUMAN:
                return True
    return False


def melee_monster_priority(agent, monsters, monster):
    _, y, x, mon, _ = monster
    ret = 1
    if agent.blstats.hitpoints > 8 or is_monster_faster(agent, monster):
        ret += 15
    if wielding_ranged_weapon(agent) and not is_monster_faster(agent, monster):
        ret -= 6
    if mon.mname in EXPLODING_MONSTERS:
        ret -= 17
    if 'were' in mon.mname:
        ret += 1
    # if not wielding_melee_weapon(agent):
    #     ret -= 5
    if mon.mname in ONLY_RANGED_SLOW_MONSTERS:
        if not consider_melee_only_ranged_if_hp_full(agent, monster):
            ret -= 100
            if mon.mname == 'floating eye':
                ret -= 10
            if mon.mname == 'gas spore':
                ret -= 5

    if mon.mname == 'gas spore':
        if spore_blast_hits_friend(agent, y, x):
            return ret - 200
        # handle a specific case when you are trapped by a gas spore
        if len(agent.get_visible_monsters()) == 1 \
                and agent.blstats.hitpoints / agent.blstats.max_hitpoints:
            dis = agent.bfs()
            for y2, x2 in zip(*np.nonzero(dis != -1)):
                if not adjacent((y, x), (y2, x2)):
                    return ret
            agent.stats_logger.log_event('melee_gas_spore')
            return 1  # a priority higher than random moving around

    return ret


WATCH_GLYPHS = frozenset(MON.from_name(n) for n in ('watchman', 'watch captain'))


def missiles_risk_the_watch(agent):
    """Minetown: a stray missile (a miss, or the rest of a volley past a dying target) that hits a peaceful
    out of sight angers the Watch (a volley killed a Mordor orc and its 2nd dagger hit a hobbit behind it;
    the watchmen killed the XL8). Melee only there."""
    gl = agent.global_logic
    if gl.minetown_level is not None and agent.current_level().key() == gl.minetown_level:
        return True
    return utils.any_in(agent.glyphs, WATCH_GLYPHS)


# hypothesis: a Rogue that throws its daggers at an adjacent monster, instead of swinging its short sword, kills
# the Dlvl 1-3 rothes, giant ants and hill orcs that end most rog-hum and rog-orc games (XL5-7) in fewer turns.
# Those monsters then get fewer free bites, and every throw trains dagger toward Expert (multishot rnd(4), +2 dmg).
#  - dothrow.c throw_obj: a Rogue gets +1 multishot with any dagger, +1 at Skilled (not when Dex <= 6) and
#    +1 more at Expert. It throws rnd(multishot) daggers, capped at the stack, and only one while confused/stunned.
#  - dothrow.c thitmonst: to-hit is -1 + dex + level, then +2 for a throwing weapon and +(3 - distance), so +2
#    adjacent, plus hitval and weapon_hit_bonus. Melee's find_roll_to_hit is 1 + abon + level.
#  - uhitm.c hmon_hitmon: every dagger that hits adds weapon_dam_bonus (and dbon, as melee does).
# Taken only when the expected volley beats one swing of the weapon the melee action would wield, and never at
# weak / ranged-only / exploding monsters. It uses the Ranger shot's priority (one above melee's). Since 3.6.0 a
# backstab (+d(level) against a fleeing monster) counts only in melee, so only in that one case does melee lose
# a bonus that this estimate leaves out.
# sources: NetHack 3.6.6 src/dothrow.c (throw_obj multishot, thitmonst), src/weapon.c (weapon_hit_bonus,
# weapon_dam_bonus), src/uhitm.c; nethackwiki.com/wiki/Rogue (Rogue +1 dagger multishot, "up to 2 at once
# immediately", backstab melee-only since 3.6.0), nethackwiki.com/wiki/Multishot, nethackwiki.com/wiki/Dagger
ROGUE_POINT_BLANK = True


def _strength_damage_bonus(strength):
    """NetHack dbon(): damage adjustment from encoded strength."""
    if strength < 6:
        return -1
    if strength < 16:
        return 0
    if strength < 18:
        return 1
    if strength == 18:
        return 2
    if strength <= 18 + 75:
        return 3
    if strength <= 18 + 90:
        return 4
    if strength < 18 + 100:
        return 5
    return 6


def rogue_volley_beats_melee(agent, launcher, ammo):
    """A Rogue (not polymorphed) whose best ranged set is a thrown, not-cursed dagger stack, and whose expected
    point-blank volley out-damages one melee swing."""
    try:
        ch = agent.character
        if not ROGUE_POINT_BLANK or ch.role != ch.ROGUE or ch.prop.polymorph or launcher is not None or \
                ammo is None or ammo.status == Item.CURSED or not ammo.is_weapon() or \
                any(abs(obj.sub) != O.P_DAGGER for obj in ammo.objs):
            return False
        skill = ch.skill_levels[O.P_DAGGER]
        dex = agent.blstats.dexterity
        multishot = 1
        if not (ch.prop.confusion or ch.prop.stun):
            multishot += 1   # Rogue throwing a dagger
            if skill >= ch.SKILL_LEVEL_EXPERT:
                multishot += 1
            if skill >= ch.SKILL_LEVEL_SKILLED and dex > 6:
                multishot += 1
        count = max(1, ammo.count)
        volley = sum(min(k, count) for k in range(1, multishot + 1)) / multishot

        dex_bonus = -3 if dex < 4 else -2 if dex < 6 else -1 if dex < 8 else max(0, dex - 14)
        skill_hit, skill_dmg = ch._get_weapon_skill_bonus(ammo)
        item_hit, item_dmg = ammo.get_weapon_bonus(False)
        throw_hit = -1 + dex_bonus + agent.blstats.experience_level + 2 + 2 + skill_hit + item_hit
        # NLE exposes both ACURRSTR (displayed 3..25) and ACURR(A_STR)
        # (encoded 3..125).  NetHack dbon() compares the encoded value.
        strength_dmg = _strength_damage_bonus(agent.blstats.strength_percentage)
        throw_dps = volley * utils.calc_dps(throw_hit, max(0, item_dmg + skill_dmg + strength_dmg))

        melee, _ = agent.inventory.get_best_melee_weapon(return_dps=True)
        main = agent.inventory.items.main_hand
        if main is not None and main.status == Item.CURSED and main.is_weapon():
            melee = main   # welded: no swap
        melee_hit, melee_dmg = ch.get_melee_bonus(melee, large_monster=False)
        melee_dps = utils.calc_dps(melee_hit, max(0, melee_dmg + strength_dmg))
        return throw_dps > melee_dps
    except Exception:
        return False


def rogue_point_blank_priority(agent, monster, default):
    """The volley's priority: one above what melee_monster_priority gives with a melee weapon in hand (16 when
    HP > 8 or the monster is faster), so it wins over the swing."""
    try:
        _, _, _, mon, _ = monster
        if mon.mname in WEAK_MONSTERS or mon.mname in ONLY_RANGED_SLOW_MONSTERS or \
                mon.mname in EXPLODING_MONSTERS:
            return default
        ret = 2
        if agent.blstats.hitpoints > 8 or is_monster_faster(agent, monster):
            ret += 15
        if 'were' in mon.mname:
            ret += 1
        return ret
    except Exception:
        return default


def ranged_priority(agent, dy, dx, monsters):
    if missiles_risk_the_watch(agent):
        return None
    ret = 11

    closest_mon_dis = float('inf')
    for monster in monsters:
        _, my, mx, mon, _ = monster
        assert my != agent.blstats.y or mx != agent.blstats.x
        if mon.mname not in WEAK_MONSTERS + ONLY_RANGED_SLOW_MONSTERS:
            closest_mon_dis = min(closest_mon_dis, line_dis_from(agent, my, mx))

    if closest_mon_dis == 1:
        ret -= 11

    launcher, ammo = agent.inventory.get_best_ranged_set()
    if ammo is None:
        return None

    if launcher is not None and not launcher.equipped:
        ret -= 5

    y, x = agent.blstats.y, agent.blstats.x
    while True:
        y += dy
        x += dx
        if not 0 <= y < agent.glyphs.shape[0] or not 0 <= x < agent.glyphs.shape[1]:
            return None

        if agent.glyphs[y, x] in G.PETS or not agent.current_level().walkable[y, x]:
            return None

        if agent.glyphs[y, x] in G.MONS:
            monster = [m for m in monsters if m[1] == y and m[2] == x]
            if not monster:
                # there is a monster that shouldn't be attacked
                return None
            assert len(monster) == 1
            _, _, _, mon, _ = monster[0]
            dis = line_dis_from(agent, y, x)
            if dis > agent.character.get_range(launcher, ammo):
                return None
            if dis in (1, 2):
                ret -= 5
            if dis == 1:
                ret -= 6
                if mon.mname == 'gas spore':  # only gas spore ?
                    ret -= 100
            # hypothesis: a gas spore's explosion (radius 1) that kills the pet costs -15 alignment
            # ("rumble of distant thunder"), after which every prayer fails and the character
            # starves (DT6A seed 1). Astra: kill spores from range only, away from pets.
            if mon.mname == 'gas spore' and spore_blast_hits_friend(agent, y, x):
                return None
            # a miss, or the rest of a multishot volley, flies on past the target: never with a pet or a
            # peaceful behind it (two unseen games hit Minetown gnomes that way: the Watch killed them)
            by, bx, reach = y, x, agent.character.get_range(launcher, ammo)
            for _ in range(max(reach - dis, 0)):
                by += dy
                bx += dx
                if not 0 <= by < agent.glyphs.shape[0] or not 0 <= bx < agent.glyphs.shape[1] or \
                        not agent.current_level().walkable[by, bx]:
                    break
                if agent.glyphs[by, bx] in G.PETS or \
                        (agent.glyphs[by, bx] in G.MONS and not any(m[1] == by and m[2] == bx for m in monsters)):
                    return None
            if dis == 1 and rogue_volley_beats_melee(agent, launcher, ammo):
                ret = rogue_point_blank_priority(agent, monster[0], ret)
            return ret, y, x, monster[0]


def get_next_states(agent, wand, y, x, dy, dx):
    if not inside(agent, y, x) or not agent.current_level().walkable[y, x]:
        can_bounce = wand.is_ray_wand()
        if not can_bounce:
            return []
        if dy == 0 or dx == 0:
            return [(y - dy, x - dx, -dy, -dx, 1.0, 1)]
        # TODO: diagonal
        side1 = (y, x - dx)
        side2 = (y - dy, x)
        side1_wall = not inside(agent, *side1) or not agent.current_level().walkable[side1]
        side2_wall = not inside(agent, *side2) or not agent.current_level().walkable[side2]
        dy1, dx1 = side2[0] - side1[0], side2[1] - side1[1]
        dy2, dx2 = side1[0] - side2[0], side1[1] - side2[1]
        if side1_wall and side2_wall:
            return [(y - dy, x - dx, -dy, -dx, 1.0, 1)]
        elif not side1_wall and not side2_wall:
            return [(y - dy, x - dx, -dy, -dx, 1 / 20, 1),
                    (y + dy1, x + dx1, dy1, dx1, 19 / 40, 1),
                    (y + dy2, x + dx2, dy2, dx2, 19 / 40, 1)]
        elif side1_wall:
            return [(y + dy1, x + dx1, dy1, dx1, 1.0, 1)]
        elif side2_wall:
            return [(y + dy2, x + dx2, dy2, dx2, 1.0, 1)]
        else:
            assert 0
    return [(y + dy, x + dx, dy, dx, 1.0, 0)]


def _simulate_wand_path(agent, wand, monsters, y, x, dy, dx, range_left, hit_targets, probability):
    if range_left < 0:
        return

    for y, x, dy, dx, next_prob, range_penalty in get_next_states(agent, wand, y, x, dy, dx):
        range_left -= range_penalty
        monster = [m for m in monsters if m[1] == y and m[2] == x]
        if monster:
            assert len(monster) == 1
            monster = monster[0]
            # For each monster hit, range decreases by 2.
            range_left -= 2
        elif inside(agent, y, x) and agent.glyphs[y, x] in G.PETS:
            monster = 'pet'
            # For each monster hit, range decreases by 2.
            range_left -= 2
        elif inside(agent, y, x) and agent.glyphs[y, x] in G.MONS and (y, x) != (agent.blstats.y, agent.blstats.x):
            # a monster that isn't a known hostile: a peaceful (a lightning bolt at a wraith hit a watch
            # captain and the Watch killed the XL10)
            monster = 'peaceful'
            range_left -= 2
        elif agent.blstats.y == y and agent.blstats.x == x:
            monster = 'self'
            range_left -= 2
        else:
            monster = None

        hit_targets[(y, x, monster)] += probability * next_prob

        _simulate_wand_path(agent, wand, monsters, y, x, dy, dx, range_left - 1, hit_targets, 1.0)


def simulate_wand_path(agent, wand, monsters, dy, dx):
    """ Returns list of tuples (y, x, hit_object, expected_hit_count).
    """
    y, x = agent.blstats.y, agent.blstats.x

    # TODO: random range left from 6 or 7 to 13
    hit_targets = defaultdict(int)
    _simulate_wand_path(agent, wand, monsters, y, x, dy, dx, 13, hit_targets, 1.0)
    for (y, x, hit_object), expected_hit_count in hit_targets.items():
        yield y, x, hit_object, expected_hit_count


_WAN_COLD = None


def _wan_cold():
    """The wand of cold object (SELF_ZAP_FIX: a Valkyrie resists her own cold bounce)."""
    global _WAN_COLD
    if _WAN_COLD is None:
        from .. import objects as O
        import nle.nethack as nh
        _WAN_COLD = O.from_name('cold', nh.WAND_CLASS)
    return _WAN_COLD


def get_potential_wand_usages(agent, monsters, dy, dx):
    ret = []
    if missiles_risk_the_watch(agent):
        return ret
    player_hp_ratio = agent.blstats.hitpoints / agent.blstats.max_hitpoints
    # TODO: also get items recursively from bags
    for item in agent.inventory.items:
        targeted_monsters = set()
        if not item.is_offensive_usable_wand() or agent.inventory.is_known_empty(item):
            continue
        priority = 0
        # print('--------------', dy, dx)
        for y, x, monster, p in simulate_wand_path(agent, item, monsters, dy, dx):
            # print(y, x, monster, p)
            if monster == 'pet':
                priority -= p * 20
            elif monster == 'peaceful':
                priority -= p * 200
            elif monster == 'self':
                # hypothesis: SELF_ZAP_FIX (ported from nhbot, where it is on for every identity): our own ray's
                # bounce costs what the ray does to us -- 6d6 fire/cold/lightning (lightning also blinds), 2d6 magic
                # missile, death -- not a flat 30 per expected pass. With +25 per pass through a 'dangerous' target
                # (giant ant, kitten, pony: out and back = +50) a wall right behind it made the zap win at any HP,
                # and the early 'killed by a bolt of fire / bolt of lightning / magic missile' losses of the grind
                # (kni s0/s11, rog-hum s7/s13, rog-orc s4, dev kni/rog-orc/tou) fit our own bolt coming back.
                # sources: nhbot/combat/fight_heur.py + nhbot/jf_config.py SELF_ZAP_FIX (10 shallow + 10 deep deaths
                # of 1023 games came right after our own ray hit us); NetHack 3.6.6 src/zap.c buzz() (rays bounce,
                # range rn1(7,7), zhitu d(6,6) for wand fire/cold/lightning, d(2,6) magic missile);
                # https://nethackwiki.com/wiki/Ray (bounces, 'be careful zapping rays near walls');
                # https://nethackwiki.com/wiki/Wand_of_lightning
                if jf_config.SELF_ZAP_FIX and not (item.objs[0] == _wan_cold() and
                                                   agent.character.role == agent.character.VALKYRIE):
                    priority -= p * jf_config.SELF_ZAP_PENALTY
                else:
                    priority -= p * 30
            elif monster is not None:
                _, y, x, mon, _ = monster
                if mon.mname in WEAK_MONSTERS:
                    priority += min(p, 1) * 1
                elif is_dangerous_monster(monster):
                    priority += p * 25
                else:
                    priority += min(p, 1) * 10
                targeted_monsters.add((y, x, monster))
        if targeted_monsters:
            # priority = priority * (1 - player_hp_ratio) - 10
            priority = priority - 15
            if jf_config.AT_ELBERETH_FIX:
                # a zap wipes nothing (zap.c has no u_wipe_engr); only hitting a monster the engraving scares
                # erases it (mon.c setmangry: 'You feel like a hypocrite')
                priority += min((elbereth_attack_penalty(agent, monsters, m) for _, _, m in targeted_monsters),
                                default=0)
            elif on_scaring_elbereth(agent, monsters):
                priority -= 100
            ret.append((priority, ('zap', dy, dx, item, targeted_monsters)))
    return ret


def at_ignorer_adjacent(agent, monsters):
    """AT_ELBERETH_FIX: a monster that melees through Elbereth stands next to us (@ humans and elves, minotaurs;
    an unseen attacker that hurt us on an intact Elbereth). Then waiting on the engraving only hands it free hits:
    base4-jf16 s4 stood 5 turns in its dig pit on Elbereth while two Green-elves took it from 65 to 12 HP -- the
    Elbereth penalty on every attack (-100) left 'wait' as fight2's best action. Attacking it doesn't cost the
    engraving's protection against it (it has none), and kills it."""
    if not jf_config.AT_ELBERETH_FIX:
        return False
    dive = agent.global_logic.dive
    y0, x0 = agent.blstats.y, agent.blstats.x
    return any(adjacent((m[1], m[2]), (y0, x0)) and dive._melee_ignores_elbereth(m[3]) for m in monsters)


def on_scaring_elbereth(agent, monsters):
    """Standing on an Elbereth that actually protects us (see at_ignorer_adjacent)."""
    return agent.inventory.engraving_below_me.lower() == 'elbereth' and not at_ignorer_adjacent(agent, monsters)


def elbereth_attack_penalty(agent, monsters, target):
    """The -100 fight2 puts on attacking from an Elbereth square. Every attack wipes letters off the engraving
    (uhitm.c attack -> u_wipe_engr(3); dothrow.c u_wipe_engr(2)), so it is right against the monsters the
    engraving holds off, but not against one it doesn't (AT_ELBERETH_FIX): that one gets hit, and the Elbereth
    is written again once it is dead (DIG_ESCAPE, fight2's elbereth action)."""
    if agent.inventory.engraving_below_me.lower() != 'elbereth':
        return 0
    if jf_config.AT_ELBERETH_FIX and target is not None and \
            agent.global_logic.dive._melee_ignores_elbereth(target[3]):
        return 0
    return -100


def focus_ignorer(agent, mon):
    """AT_ELBERETH_FIX + AT_FOCUS: hit the monster that ignores Elbereth first while an Elbereth could hold off the
    rest (on one already, or able to write one; not in Gehennom, not blind). The first swing at it smudges the
    engraving, and fight2 then turned on the crowd: harness Big Room seeds 16 and 37 hit a yeti, a jaguar, a hill
    orc and a red naga with the Woodland-/Green-elf still alive, which kept the dig out off (an adjacent ignorer
    stops it) until the XL7 was down to 3-11 HP. With the ignorer dead the dig out writes Elbereth and digs on."""
    if not jf_config.AT_ELBERETH_FIX or not jf_config.AT_FOCUS or in_gehennom(agent) or agent.character.prop.blind:
        return False
    if not agent.global_logic.dive._melee_ignores_elbereth(mon):
        return False
    return agent.inventory.engraving_below_me.lower() == 'elbereth' or agent.can_engrave()


def in_gehennom(agent):
    """monmove.c onscary(): Elbereth scares nothing in Gehennom (Inhell); engraving it there only hands out a
    free hit, and waiting on it is standing still under attack."""
    return jf_config.GEHENNOM_DIVE and agent.current_level().dungeon_number == 1


def elbereth_action(agent, monsters):
    if agent.inventory.engraving_below_me.lower() == 'elbereth':
        return []
    if in_gehennom(agent):
        return []
    if not agent.can_engrave():
        return []
    adj_monsters_count = 0
    dive = agent.global_logic.dive
    for monster in monsters:
        _, my, mx, mon, _ = monster
        if mon.mname in ONLY_RANGED_SLOW_MONSTERS:
            continue
        if not adjacent((my, mx), (agent.blstats.y, agent.blstats.x)):
            continue
        if jf_config.AT_ELBERETH_FIX and dive._melee_ignores_elbereth(mon):
            continue   # the engraving doesn't hold it off: writing it only hands it a free hit
        multiplier = np.clip(20 / agent.blstats.hitpoints, 1.0, 1.5)
        if is_monster_faster(agent, monster):
            multiplier *= 2
        if mon in WEAK_MONSTERS:
            adj_monsters_count += 0.1 * multiplier
            continue
        adj_monsters_count += 1 * multiplier
        if is_dangerous_monster(monster):
            adj_monsters_count += 2 * multiplier

    player_hp_ratio = (agent.blstats.hitpoints / agent.blstats.max_hitpoints) ** 0.5
    if agent.blstats.hitpoints < 30 and adj_monsters_count > 0:
        return [(-15 + 20 * adj_monsters_count * (1 - player_hp_ratio), ('elbereth',))]
    return []


def wait_action(agent, monsters):
    # RANGED_ON_ELB: no waiting on Elbereth while something shoots at us (it only stops melee)
    if agent.global_logic.dive.shot_recently():
        return []
    if on_scaring_elbereth(agent, monsters) and not in_gehennom(agent):
        player_hp_ratio = agent.blstats.hitpoints / agent.blstats.max_hitpoints
        priority = 30 - player_hp_ratio * 40
        return [(priority, ('wait',))]
    return []


def get_available_actions(agent, monsters):
    actions = []

    # melee attack actions
    for monster in monsters:
        _, y, x, mon, _ = monster
        if adjacent((y, x), (agent.blstats.y, agent.blstats.x)):
            priority = melee_monster_priority(agent, monsters, monster)
            priority += elbereth_attack_penalty(agent, monsters, monster)
            if focus_ignorer(agent, mon):
                priority += jf_config.AT_FOCUS
            dy = y - agent.blstats.y
            dx = x - agent.blstats.x
            # hypothesis: refusing all bare contact with cockatrices prevents
            # instant petrification, while leaving ranged attacks and retreat
            # available to both armed and unarmed characters.
            bare_handed = agent.inventory.items.main_hand is None
            bare_hands = agent.inventory.items.gloves is None
            bare_feet = agent.inventory.items.boots is None
            if ord(mon.mlet) == MON.S_COCKATRICE and bare_handed and bare_hands:
                if not bare_feet:
                    actions.append((priority, ('kick', dy, dx)))
            else:
                actions.append((priority, ('melee', dy, dx)))

    # ranged attack actions
    for dy, dx in product([-1, 0, 1], [-1, 0, 1]):
        if dy != 0 or dx != 0:
            ranged_pr = ranged_priority(agent, dy, dx, monsters)
            if ranged_pr is not None:
                pri, y, x, monster = ranged_pr
                pri += elbereth_attack_penalty(agent, monsters, monster)
                if all(monster[3].mname in ONLY_RANGED_SLOW_MONSTERS for monster in monsters):
                    pri += 10
                actions.append((pri, ('ranged', dy, dx)))

            actions.extend(get_potential_wand_usages(agent, monsters, dy, dx))

    to_pickup = decide_what_to_pickup(agent)
    if to_pickup:
        actions.append((15, ('pickup', to_pickup)))

    actions.extend(elbereth_action(agent, monsters))
    actions.extend(wait_action(agent, monsters))

    return actions


def decide_what_to_pickup(agent):
    # never a shop's goods: an unseen game picked up a for-sale dagger (Grimtooth), threw it, owed 2204
    # zorkmids and was killed by the shopkeeper
    projectiles_below_me = [i for i in agent.inventory.items_below_me
                            if (i.is_thrown_projectile() or i.is_fired_projectile()) and
                            i.shop_status == Item.NOT_SHOP]
    my_launcher, ammo = agent.inventory.get_best_ranged_set(additional_ammo=[i for i in projectiles_below_me])
    to_pickup = []
    for item in agent.inventory.items_below_me:
        if item.shop_status != Item.NOT_SHOP:
            continue
        if item.is_thrown_projectile() or (my_launcher is not None and item.is_fired_projectile(launcher=my_launcher)):
            to_pickup.append(item)
    return to_pickup


def goto_action(agent, priority, monsters):
    values = []
    walkable = agent.current_level().walkable
    for dy, dx in [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]:
        y, x = agent.blstats.y - dy, agent.blstats.x - dx
        if not 0 <= y < walkable.shape[0] or not 0 <= x < walkable.shape[1]:
            continue
        if not np.isnan(priority[y, x]):
            values.append(priority[y, x])
    if len(set(values)) > 1:
        return []

    assert monsters
    for monster in monsters:
        _, my, mx, mon, _ = monster
        if not adjacent((agent.blstats.y, agent.blstats.x), (my, mx)):
            # and not mon.mname in ONLY_RANGED_SLOW_MONSTERS:
            return [(1, ('go_to', my, mx))]
    # every monster adjacent and nothing to do (e.g. no weapon known): fight2 falls back to moving/waiting
    return []


def get_corridors_priority_map(walkable):
    k = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
    wall_count = signal.convolve2d((~walkable).astype(int), k, boundary='symm', mode='same')
    corridor_mask = (wall_count == 6).astype(int)
    corridor_mask[~walkable] = 0
    corridor_dilated = signal.convolve2d(corridor_mask.astype(int), k, boundary='symm', mode='same')
    return corridor_mask + corridor_dilated >= 1


def get_priorities(agent):
    """ Returns a pair (move priority heatmap, other actions (with priorities) list) """
    walkable = agent.current_level().walkable
    priority = np.zeros(walkable.shape, dtype=float)
    # without the monsters a stalled fight let go of (jf_config.FIGHT_STALL_TURNS)
    monsters = agent.fight_monsters()
    for m in monsters:
        draw_monster_priority_positive(agent, m, priority, walkable)
    for m in monsters:
        draw_monster_priority_negative(agent, m, priority, walkable)
    priority[~walkable] = float('nan')

    # TODO: figure out how to use corridors priority so that it improves the score
    # if len([m for m in monsters if m[3].mname not in chain(ONLY_RANGED_SLOW_MONSTERS, WEAK_MONSTERS)]) >= 4:
    #     priority += get_corridors_priority_map(walkable)
    # for _, _, _, mon, _ in monsters:
    #     if ord(mon.mlet) == MON.S_ANT:
    #         priority += get_corridors_priority_map(walkable)
    #         break

    # use relative priority to te current position
    priority -= priority[agent.blstats.y, agent.blstats.x]

    actions = get_available_actions(agent, monsters)
    if not any(a[1][0] in ('melee', 'kick', 'ranged') for a in actions):
        actions.extend(goto_action(agent, priority, monsters))
    return priority, actions


def get_move_actions(agent, dis, move_priority_heatmap):
    """ Returns list of tuples (priority, ('move', dy, dx)) """
    ret = []
    for dy, dx in [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]:
        y, x = agent.blstats.y + dy, agent.blstats.x + dx
        if not 0 <= y < dis.shape[0] or not 0 <= x < dis.shape[1]:
            continue
        if not dis[y, x] == 1:
            continue
        # a monster left out of the fight (the Valley's graveyard sleepers, VALLEY_GRAVE_FILTER) still occupies its
        # square: moving there panics ('Monster on a next tile') in a loop
        if in_gehennom(agent) and agent.monster_tracker.monster_mask[y, x]:
            continue

        if not np.isnan(move_priority_heatmap[y, x]):
            ret.append((move_priority_heatmap[y, x], ('move', dy, dx)))
    return ret

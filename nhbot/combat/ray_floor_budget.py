"""Bound positive credits under the inherited observed-map ray model.

This is not an exact NLE trajectory simulator. Foreground terrain glyphs can
include remembered cells. Unknown underlying terrain and fire pool/moat or ice
ambiguity receive no extra loss. Legacy negative contacts are retained verbatim.
"""
from collections import defaultdict


def bound_known_floor_rewards(agent, wand, monsters, dy, dx, paths,
                             next_states, inside, SS, G):
    prop = getattr(getattr(agent, 'character', None), 'prop', None)
    if (prop is None or not hasattr(prop, 'blind') or not hasattr(prop, 'hallu')
            or prop.blind or prop.hallu or not wand.is_ray_wand()):
        return paths
    objs = getattr(wand, 'objs', ())
    kind = getattr(objs[0], 'name', None) if len(objs) == 1 else None
    if kind not in ('fire', 'cold'):
        return paths
    admitted = {SS.S_fountain} if kind == 'fire' else {SS.S_pool, SS.S_lava, SS.S_water}
    floors = {}
    for y, x, _, _ in paths:
        if inside(agent, y, x):
            glyph = agent.glyphs[y, x]
            if glyph in admitted:
                floors[y, x] = glyph
    if not floors:
        return paths
    rewards = defaultdict(float)
    by_pos = {(m[1], m[2]): m for m in monsters}

    def walk(y, x, sy, sx, left, probability, charged):
        if left < 0:
            return
        for yy, xx, ddy, ddx, p, penalty in next_states(agent, wand, y, x, sy, sx):
            remaining = left - penalty
            pos = yy, xx
            glyph = floors.get(pos)
            history = charged
            stop = kind == 'cold' and glyph == SS.S_water
            if glyph is not None and not stop and pos not in charged:
                remaining -= 1 if kind == 'fire' else 3
                # Cold changes pool/moat/drawbridge/lava to ice/floor. For fire
                # assume a fountain dries on its first encounter; if it does
                # not dry, further range losses can only reduce reach again.
                history = charged | {pos}
            monster = by_pos.get(pos)
            if monster is not None:
                remaining -= 2
            elif inside(agent, yy, xx) and agent.glyphs[yy, xx] in G.PETS:
                monster = 'pet'; remaining -= 2
            elif (inside(agent, yy, xx) and agent.glyphs[yy, xx] in G.MONS
                  and pos != (agent.blstats.y, agent.blstats.x)):
                monster = 'peaceful'; remaining -= 2
            elif pos == (agent.blstats.y, agent.blstats.x):
                monster = 'self'; remaining -= 2
            if monster is not None and not isinstance(monster, str):
                # buzz handles the current-cell monster even after a negative
                # floor range modifier. Stop only its continuation afterward.
                rewards[yy, xx, monster] += probability * p
            if not stop:
                walk(yy, xx, ddy, ddx, remaining - 1, probability * p, history)

    walk(agent.blstats.y, agent.blstats.x, dy, dx, 13, 1., frozenset())
    return [(y, x, monster, p if monster is None or isinstance(monster, str)
             else min(p, rewards[y, x, monster])) for y, x, monster, p in paths]

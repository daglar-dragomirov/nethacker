"""Research draft: conservative contact penalty over unknown hit probabilities.

The caller supplies the inherited terrain kernel and visible encounter costs.
This is not an exact simulator and does not infer individual armor/reflectors.
"""
from functools import lru_cache


def miss_contact_penalty_bound(kernel, agent, wand, direction, budget,
                               encounters, hazard_costs, origin):
    """Bound expected contact penalty for any hit probabilities in[0,1].

    Each visible creature may be hit (extra range cost2) or missed (cost0).
    Charge hazard contact regardless of hit, then choose the larger continuation
    for each encounter. Nonnegative geometric branch weights remain unchanged.
    The retained inclusive parent budget decreases on every advance, so the
    cached state graph is acyclic. Hidden reflection and floor effects remain
    outside the inherited model.
    """
    encounters=frozenset(encounters)

    @lru_cache(maxsize=None)
    def value(y,x,dy,dx,left):
        if left<0:
            return 0.
        total=0.
        for yy,xx,ddy,ddx,p,pen in kernel(agent,wand,y,x,dy,dx):
            assert p>=0 and pen>=0
            if not p:
                continue
            remaining=left-pen-1
            future=value(yy,xx,ddy,ddx,remaining)
            cell=(yy,xx)
            if cell in encounters:
                future=max(future,value(yy,xx,ddy,ddx,remaining-2))
            total+=p*(hazard_costs.get(cell,0.)+future)
        return total

    result=value(*origin,*direction,budget)
    return result,value.cache_info().currsize

"""Selector research adapter, outside all game trees and frozen protocols."""


def ray_miss_extra_penalty(agent,item,monsters,dy,dx,paths,kernel,G,inside,
                           self_penalty):
    if not item.is_ray_wand():
        return 0.,0
    budget=13
    origin=(agent.blstats.y,agent.blstats.x)
    hostile={(m[1],m[2]) for m in monsters}
    encounters=set(hostile)
    hazards={}
    # Parent inclusive13 convention has at most14 coordinate advances.
    # Only visible glyphs in the bounded reachable square can contribute.
    radius=budget+1
    for y in range(max(0,origin[0]-radius),min(agent.glyphs.shape[0],origin[0]+radius+1)):
        for x in range(max(0,origin[1]-radius),min(agent.glyphs.shape[1],origin[1]+radius+1)):
            cell=(y,x)
            if cell in hostile:
                continue
            glyph=agent.glyphs[y,x]
            if glyph in G.PETS:
                hazards[cell]=20.
            elif glyph in G.MONS and cell!=origin:
                hazards[cell]=200.
            elif cell==origin:
                hazards[cell]=float(self_penalty)
            else:
                continue
            encounters.add(cell)
    inherited=sum(p*(20. if target=='pet' else 200. if target=='peaceful'
                     else self_penalty if target=='self' else 0.)
                  for _,_,target,p in paths)
    bound,states=miss_contact_penalty_bound(kernel,agent,item,(dy,dx),budget,
                                           encounters,hazards,origin)
    # Numeric roundoff can never weaken an inherited negative priority.
    return max(0.,bound-inherited),states

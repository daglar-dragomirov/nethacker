"""Pure ray/beam threat models from open69f6; use intact Evidence monster model."""
import math
import re
DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
RANGES = tuple(range(7, 14))
P_MON_HIT = 0.95
P_SELF_HIT = 0.95
BCHANCE = 75

def ray_outcomes(zap_pos, hero, d, mons, ranges=RANGES, p_mon=P_MON_HIT, p_self=P_SELF_HIT, bchance=BCHANCE):
    """Simulate our sleep ray from `hero` (y, x) in direction d = (dy, dx) as zap.c dobuzz does, averaged over the
    ranges. zap_pos[y][x]: the ray passes the square (else it bounces there); mons: {(y, x): kind} for every creature
    on the map (any kind). Returns (P(the ray hits us), {pos: P(it hits the creature there at least once)})."""
    h, w = len(zap_pos), len(zap_pos[0])
    hit_p = {}
    self_p = 0.0

    def ok(y, x):
        return (y, x) == hero or (0 <= y < h and 0 <= x < w and bool(zap_pos[y][x]))

    def run(y, x, dy, dx, rng, prob, hit):
        nonlocal self_p
        if prob < 1e-5:
            return
        while rng > 0:
            rng -= 1
            ly, lx = y, x
            y, x = y + dy, x + dx
            if (y, x) in mons and ok(y, x):
                if (y, x) not in hit:
                    # P_MON miss: the ray flies on with its range; hit: -2 and the creature is marked
                    run(y, x, dy, dx, rng, prob * (1 - p_mon), hit)
                    prob *= p_mon
                    hit = hit | {(y, x)}
                else:
                    # already hit once (asleep): it still costs range when the ray hits it again
                    run(y, x, dy, dx, rng, prob * (1 - p_mon), hit)
                    prob *= p_mon
                rng -= 2
            elif (y, x) == hero and rng >= 0:
                self_p += prob * p_self / len(ranges)
                prob *= 1 - p_self
                if prob <= 1e-6:
                    return
            if not ok(y, x):
                rng -= 1
                if dy == 0 or dx == 0:
                    dy, dx = -dy, -dx
                    continue
                side1 = ok(ly, x)       # (sx, lsy): keep x, flip dy
                side2 = ok(y, lx)       # (lsx, sy): keep y, flip dx
                rev = prob / bchance
                run(y, x, -dy, -dx, rng, rev, hit)
                rest = prob - rev
                if side1 and side2:
                    run(y, x, -dy, dx, rng, rest / 2, hit)
                    dx = -dx
                    prob = rest / 2
                elif side1:
                    dy = -dy
                    prob = rest
                elif side2:
                    dx = -dx
                    prob = rest
                else:
                    dy, dx = -dy, -dx
                    prob = rest
        for pos in hit:
            hit_p[pos] = hit_p.get(pos, 0.0) + prob / len(ranges)

    for r in ranges:
        run(hero[0], hero[1], d[0], d[1], r, 1.0, frozenset())
    return self_p, hit_p

def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def threat(hostiles, hp, ac, depth, xl, turns):
    """P(the melee of `hostiles` [(name, distance)] deals >= hp within `turns` turns), and each one's mean damage
    over them (same order). A monster d squares away joins after (d - 1) / speed turns."""
    from .nhmodel.prayer import monster_turn_damage
    mean = var = 0.0
    each = []
    for name, dist in hostiles:
        m1, v1, spd = monster_turn_damage(name, int(ac), int(depth), int(xl))
        t = max(0.0, turns - max(0, dist - 1) / max(spd, 0.25))
        each.append(m1 * spd * t)
        mean += m1 * spd * t
        var += v1 * spd * t
    if mean <= 0:
        return 0.0, each
    return 1.0 - _phi((hp - 0.5 - mean) / math.sqrt(max(var, 1.0))), each

def _cheb(a, b):
    return max(abs(int(a[0]) - int(b[0])), abs(int(a[1]) - int(b[1])))

def charges(item):
    """Known charges of a wand from its text '(0:6)', else None."""
    m = re.search(r'\((-?\d+):(-?\d+)\)', getattr(item, 'text', '') or '')
    return int(m.group(2)) if m else None

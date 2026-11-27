"""Opportunity items (slim port from hed 6ee98468 opp_items.py): what DEEP_ITEMS needs --

- instrument_kind / bugle_ok / scare_radius2 / play: scare instruments and unknown horns (a blown
  horn's outcome is learned by glyph: 'scare' / 'ray' / 'plenty')
- longest_free_dir / free_run: the safest direction for a possible ray
- state() + note_message: the per-agent learning store (playing -> scare sound)

The genocide / tengu / camera / item-priority parts of hed's module are not ported (unused here).
"""

import nle.nethack as nh

from . import jf_config
from . import objects as O
from .glyph import MON, SS

TOOLED_HORN = O.from_name('tooled horn')
FROST_HORN = O.from_name('frost horn')
FIRE_HORN = O.from_name('fire horn')
HORN_OF_PLENTY = O.from_name('horn of plenty')
LEATHER_DRUM = O.from_name('leather drum')
EARTHQUAKE_DRUM = O.from_name('drum of earthquake')
CAMERA = O.from_name('expensive camera')
BUGLE = O.from_name('bugle')
# BUGLE_SCARE: the mercenaries a bugle wakes and turns hostile (music.c awaken_soldiers: is_mercenary)
_MERCENARIES = frozenset(('soldier', 'sergeant', 'lieutenant', 'captain', 'watchman', 'watch captain'))
HORNS = frozenset((TOOLED_HORN, FROST_HORN, FIRE_HORN, HORN_OF_PLENTY))
DRUMS = frozenset((LEATHER_DRUM, EARTHQUAKE_DRUM))

_SCARE_SOUNDS = ('You produce a frightful, grave sound', 'You beat a deafening row', 'You pound on the drum',
                 'You blow into the horn', 'heavy, thunderous rolling') + \
    (('You extract a loud noise from', 'You blow into the bugle') if jf_config.BUGLE_SCARE else ())
_DIRS = {'n': (-1, 0), 's': (1, 0), 'e': (0, 1), 'w': (0, -1), 'ne': (-1, 1), 'nw': (-1, -1), 'se': (1, 1),
         'sw': (1, -1)}
_DIR_KEYS = {'n': 'k', 's': 'j', 'e': 'l', 'w': 'h', 'ne': 'u', 'nw': 'y', 'se': 'n', 'sw': 'b', '>': '>', '<': '<',
             '.': '.'}


class OppState:
    def __init__(self):
        self.horn_glyphs = {}        # instrument glyph -> 'scare' | 'ray' | 'plenty' (what blowing it did)
        self.playing = None          # (step, glyph) of the instrument just played
        self.empty = set()           # camera texts that said 'Nothing happens'
        self.last_msg_step = -1


def state(agent):
    st = getattr(agent, '_opp', None)
    if st is None:
        st = agent._opp = OppState()
    return st


def _log(agent, msg):
    agent.log(f'OPP {msg}')


def note_message(agent):
    """agent.update, every observation (DEEP_ITEMS on): what an instrument turned out to be."""
    msg = agent.single_message or ''
    st = state(agent)
    if not msg or st.last_msg_step == agent.step_count:
        return
    st.last_msg_step = agent.step_count
    try:
        if st.playing is not None and agent.step_count - st.playing[0] <= 6 and \
                any(s in msg for s in _SCARE_SOUNDS):
            st.horn_glyphs.setdefault(st.playing[1], 'scare')
    except Exception as e:   # learning must never break the step loop
        agent.log(f'OPP note_message failed: {e!r}')


def instrument_kind(agent, item):
    """'scare' (tooled horn, any drum, a horn that scared when blown), 'horn' (an unknown horn: tooled 5/11, frost
    2/11, fire 2/11, plenty 2/11), 'camera', or None."""
    if item.category != nh.TOOL_CLASS or not item.objs or 'unpaid' in (item.text or ''):
        return None
    objs = set(item.objs)
    if objs <= DRUMS:
        return 'scare'
    if item.is_unambiguous():
        if item.object == TOOLED_HORN:
            return 'scare'
        if item.object == BUGLE:
            return 'scare' if jf_config.BUGLE_SCARE and bugle_ok(agent) else None
        if item.object == CAMERA:
            return None if item.text in state(agent).empty else 'camera'
        return None
    if objs <= HORNS:
        what = state(agent).horn_glyphs.get(item.glyphs[0] if item.glyphs else None)
        if what == 'scare':
            return 'scare'
        if what is not None:
            return None   # a horn of plenty, or a ray horn the game has named by now
        return 'horn'
    return None


def bugle_ok(agent):
    """BUGLE_SCARE: a bugle also wakes every mercenary on the level and makes them hostile (music.c awaken_soldiers):
    never on the castle level (its barracks sleep ~40 soldiers) nor with a peaceful watchman or soldier in view (a
    town's watch turns on us)."""
    try:
        dive = agent.global_logic.dive
        key = agent.current_level().key()
        if dive.castle.castle_key is not None and key == dive.castle.castle_key:
            # CL_BUGLE_WEST (castle-lift, main's idea): the castle's soldiers wake and turn hostile, but on the west side
            # before any crossing they can't reach us -- the drawbridge is raised, the towers open inward, the barracks
            # and the trap-door hall behind locked doors -- while a minotaur flees the bugle (R176: 14/20 vs 1/20)
            if not jf_config.CL_BUGLE_WEST:
                return False
            castle = dive.castle
            mx, _ = castle._pos()
            from .castle_logic import WEST_COURTYARD
            if castle.committed() or not (mx < 0 or castle._pos() in WEST_COURTYARD):
                return False
        peaceful = agent.monster_tracker.peaceful_monster_mask
        for _, y, x, mon, _ in agent.get_visible_monsters():
            if getattr(mon, 'mname', '') in _MERCENARIES and peaceful[y, x]:
                return False
        return True
    except Exception:
        return False


def scare_radius2(agent, item):
    """distu below which blowing it makes a monster flee (music.c: awaken_monsters(d) scares within d/3)."""
    xl = int(agent.blstats.experience_level)
    objs = set(item.objs)
    if objs <= DRUMS:
        if item.is_unambiguous() and item.object == EARTHQUAKE_DRUM:
            return 10 ** 6   # a charged one shakes the level (an empty one is a mundane drum: XL*5)
        return xl * 40 // 3
    return xl * 10


def play(agent, item, ray_dir):
    """Apply an instrument: 'Improvise?' -> y (music.c: 'n' goes to the tune prompt), 'In what direction?' (a charged
    frost/fire horn's ray) -> ray_dir. Returns what happened: dict(improvise, direction, msg)."""
    from nle.nethack import actions as A
    st = state(agent)
    letter = agent.inventory.items.get_letter(item)
    seen = dict(improvise=False, direction=False)
    st.playing = (agent.step_count, item.glyphs[0] if item.glyphs else None)

    def gen():
        if 'What do you want to use or apply?' not in agent.single_message:
            return
        yield letter
        for _ in range(8):
            msg = agent.single_message or ''
            if 'Improvise?' in msg and not seen['improvise']:
                seen['improvise'] = True
                yield 'y'
                continue
            if 'In what direction?' in msg and not seen['direction']:
                seen['direction'] = True
                yield _DIR_KEYS.get(ray_dir, '>')
                continue
            misc = agent._observation['misc']
            if misc[2] and not misc[1]:
                yield ' '
                continue
            return

    with agent.atom_operation():
        agent.step(A.Command.APPLY, gen())
    msg = agent.message or ''
    g = item.glyphs[0] if item.glyphs else None
    if not set(item.objs) <= DRUMS and not item.is_unambiguous():
        if seen['direction']:
            st.horn_glyphs[g] = 'ray'
        elif not seen['improvise'] and not agent.character.prop.confusion and not agent.character.prop.stun and \
                not agent.character.prop.hallu:
            st.horn_glyphs[g] = 'plenty'   # no instrument prompt: a horn of plenty (apply.c hornoplenty)
        elif any(s in msg for s in _SCARE_SOUNDS):
            st.horn_glyphs[g] = 'scare'
    _log(agent, f'played {item.text!r} ({letter}) ray {ray_dir}: improvise={seen["improvise"]} '
                f'direction={seen["direction"]} -> {msg[:160]!r}')
    agent.inventory.items.update(force=True)
    return dict(seen, msg=msg)


def free_run(agent, sy, sx, limit=20):
    """Walkable squares from us in direction (sy, sx) before a wall or the edge (a ray's room to die out)."""
    level = agent.current_level()
    y, x = int(agent.blstats.y), int(agent.blstats.x)
    h, w = level.walkable.shape
    n = 0
    while n < limit:
        y, x = y + sy, x + sx
        if not (0 <= y < h and 0 <= x < w) or not level.walkable[y, x]:
            break
        n += 1
    return n


def longest_free_dir(agent):
    """The compass direction with the longest free run (a possible ray's safest way out), and that run."""
    best = max(_DIRS.items(), key=lambda kv: free_run(agent, *kv[1]))
    return best[0], free_run(agent, *best[1])

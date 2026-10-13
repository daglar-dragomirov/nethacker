"""Undeployed observed-owner adapter for the next whole Public supply design.

NLE1.3.0 pager.c look_at_monster and do_name.c x_monnam expose a normal
shopkeeper as 'peaceful NAME', or 'peaceful NAME the invisible shopkeeper'.
Query before PAY only: WHATIS inside a PAY targeting prompt would corrupt it.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class KeeperObservation:
    level_key: tuple
    shop_id: int
    owner_name: str
    position: tuple
    turn: int
    step_serial: int
    description: str


def _context(agent):
    b = agent.blstats
    return agent.current_level().key(), b.y, b.x, b.time


def observe_named_keeper(agent, record, owner_name, keeper_glyphs):
    """Observe one named keeper strictly within its anchored shop interior.

    Never resolve from geometry alone, an entrance, a stale peaceful mask or an
    anonymous glyph. Exceptions/preemption from the existing map query propagate.
    The caller must provide an owner observed in a greeting, not infer a name.
    """
    if not owner_name or getattr(record, 'owner_ambiguous', False) or \
            getattr(record, 'owner_name', None) != owner_name or \
            agent.character.prop.hallu or agent.character.prop.blind:
        return None
    before = _context(agent)
    level = agent.current_level()
    bindings = [r for r in level.shops.records.values()
                if getattr(r, 'owner_name', None) == owner_name]
    if len(bindings) != 1 or bindings[0] is not record:
        return None
    descriptions = agent.monster_tracker.take_all_monsters()
    if _context(agent) != before:
        return None
    allowed = {'peaceful ' + owner_name,
               'peaceful ' + owner_name + ' the invisible shopkeeper'}
    matching = [(pos, text) for pos, text in descriptions.items() if text in allowed]
    if len(matching) != 1:
        return None
    position, description = matching[0]
    y, x = position
    if not record.interior[y, x] or agent.glyphs[y, x] not in keeper_glyphs or \
            not agent.monster_tracker.peaceful_monster_mask[y, x]:
        return None
    return KeeperObservation(before[0], record.shop_id, owner_name, (int(y), int(x)),
                             int(before[3]), int(agent.step_count), description)


def pay_target_from_observation(agent, record, observed, keeper_glyphs):
    """Check the saved pre-PAY observation without issuing another map command.

    A free menu action may increment step_count, so freshness uses game turn,
    level and anchored owner context. A later PAY reply must separately match the
    owner and operation token using observed_shop_owner_policy.
    """
    if observed is None or agent.current_level().key() != observed.level_key or \
            agent.blstats.time != observed.turn or record.shop_id != observed.shop_id or \
            getattr(record, 'owner_name', None) != observed.owner_name or \
            getattr(record, 'owner_ambiguous', False) or \
            agent.character.prop.hallu or agent.character.prop.blind:
        return None
    y, x = observed.position
    if not record.interior[y, x] or agent.glyphs[y, x] not in keeper_glyphs or \
            not agent.monster_tracker.peaceful_monster_mask[y, x]:
        return None
    return observed.position

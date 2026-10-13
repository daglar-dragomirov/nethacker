"""Whole Public-parent Wizard book upkeep. Draft until imported-engine checks.

Owned-book and interval mechanisms adapted from Luab b16051f (MIT retained).
No additional utility casts, prayer retiming, shop routes or armor removal.
"""
import nle.nethack as nh
from nle.nethack import actions as A

from . import jf_config
from .character import ALL_SPELL_CATEGORIES, ALL_SPELL_NAMES
from .glyph import Hunger
from .item.item import Item
from .observed_spell_memory_policy import USEFUL, Study, eligible, parse_row, refine
from .strategy import Strategy


def parse_catalog(character):
    agent = character.agent
    old = getattr(character, 'observed_spell_catalog', None) or {}
    character.known_spells = {}
    character.spell_fail_chance = {}
    character.observed_spell_catalog = None
    with agent.atom_operation():
        agent.step(A.Command.CAST)
        if not agent.popup:
            if "You don't know any spells" in agent.message:
                character.observed_spell_catalog = {}
            return
        if (agent.popup[0] != 'Choose which spell to cast' or
                not agent.popup[1].startswith('Name')):
            raise ValueError('Invalid cast popup: ' + repr(agent.popup))
        catalog = {}
        for line in agent.popup[2:]:
            observed = parse_row(line, agent.blstats.time)
            if observed.name not in ALL_SPELL_NAMES or observed.category not in ALL_SPELL_CATEGORIES:
                raise ValueError('Unknown spell row: ' + repr(line))
            spell = refine(old.get(observed.name), observed)
            catalog[spell.name] = spell
            if jf_config.FB_SANITY and spell.retention == (0, 0):
                continue
            character.known_spells[spell.name] = spell.letter
            character.spell_fail_chance[spell.name] = spell.failure
        character.observed_spell_catalog = catalog
    agent.step(A.Command.ESC)


def useful_book(item):
    return (item.category == nh.SPBOOK_CLASS and item.is_unambiguous() and
            item.object.name in USEFUL and item.shop_status == Item.NOT_SHOP and
            item.status in (Item.BLESSED, Item.UNCURSED))


def keep_books(agent, items):
    if agent.character.role != agent.character.WIZARD:
        return []
    kept, names = [], set()
    for item in sorted(items, key=lambda x: (not useful_book(x),
                                           USEFUL.index(x.object.name) if useful_book(x) else 99,
                                           x.unit_weight(with_content=False))):
        if useful_book(item) and item.object.name not in names:
            names.add(item.object.name)
            kept.append(item)
    return kept[:2]


def context_safe(agent):
    ch, bl = agent.character, agent.blstats
    prop = ch.prop
    conditions = int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION])
    deadly = conditions & (nh.BL_MASK_STONE | nh.BL_MASK_SLIME | nh.BL_MASK_STRNGL |
                           nh.BL_MASK_FOODPOIS | nh.BL_MASK_TERMILL)
    return (ch.role == ch.WIZARD and bl.hitpoints == bl.max_hitpoints and
            bl.hunger_state <= Hunger.NOT_HUNGRY and bl.carrying_capacity == 0 and
            not any((prop.blind, prop.confusion, prop.stun, prop.hallu, prop.polymorph, deadly)) and
            not agent.get_visible_monsters() and not agent.hands_welded() and
            not agent.current_level().shop[bl.y, bl.x])


def readable(agent, item):
    if not useful_book(item) or getattr(item.object, 'desc', None) == 'dull':
        return False
    return (item.status == Item.BLESSED or
            agent.blstats.intelligence + 4 + agent.blstats.experience_level // 2 -
            2 * item.object.level >= 20)


@Strategy.wrap
def upkeep(inventory):
    agent = inventory.agent
    books = [i for i in inventory.items if readable(agent, i)]
    retry = getattr(agent, '_observed_book_retry', {})
    if not books or not context_safe(agent) or agent.blstats.time < getattr(agent, '_observed_book_probe', -1):
        yield False
        return
    yield True
    agent._observed_book_probe = agent.blstats.time + 250
    agent.character.parse_spellcast_view()
    catalog = getattr(agent.character, 'observed_spell_catalog', None)
    if catalog is None or not context_safe(agent):
        return
    books = [i for i in inventory.items if readable(agent, i) and
             eligible(catalog.get(i.object.name), i.object.name, agent.blstats.time) and
             agent.blstats.time >= retry.get(i.object.name, -1)]
    if not books:
        return
    book = min(books, key=lambda i: USEFUL.index(i.object.name))
    name = book.object.name
    letter = inventory.items.get_letter(book)
    retry[name] = agent.blstats.time + 250
    agent._observed_book_retry = retry
    operation = Study(name, agent.blstats.time)
    agent._observed_book_operation = operation
    history_start = len(agent._message_history)

    def answers():
        if 'What do you want to read?' not in agent.single_message:
            return
        yield letter
        if 'difficult to comprehend' in agent.single_message:
            yield 'n'

    try:
        with agent.atom_operation():
            agent.step(A.Command.READ, answers())
        for message in agent._message_history[history_start:]:
            operation.observe(message, agent.blstats.time)
        operation.input_returned()
        if operation.may_query_completion:
            agent.character.parse_spellcast_view()
            fresh = getattr(agent.character, 'observed_spell_catalog', None)
            operation.verify(fresh.get(name) if fresh is not None else None)
        if operation.terminal == 'unusable':
            retry[name] = agent.blstats.time + 20000
    finally:
        # A scheduler exception must propagate; it cannot mark a read complete.
        operation.input_returned()
        agent.log('OBSERVED_SPELL_READ ' + name + ': ' + str(operation.terminal) +
                  ' verified=' + str(operation.verified))

"""Experimental observed-spell upkeep bridge for the exact nhbot parent.

Own integration; source contracts and donor review are recorded in CHANGES.
No hidden timer, alignment, unknown-book or stack posterior is used.
"""
import re

import nle.nethack as nh
from nle.nethack import actions as A

from .glyph import Hunger
from .item.item import Item
from .known_spell_sustain_policy import Book, Player, Spell, Study, USEFUL, refresh_eligible, utility_spell
from .strategy import Strategy


def state(agent):
    if not hasattr(agent, '_spell_sustain'):
        agent._spell_sustain = {'probe_until':-1, 'upkeep_until':-1, 'attempts':{}, 'study':None}
    return agent._spell_sustain


def player(agent):
    b=agent.blstats
    prop=agent.character.prop
    hostile=agent.get_visible_monsters()
    conditions=int(agent.last_observation['blstats'][nh.NLE_BL_CONDITION])
    deadly=conditions & (nh.BL_MASK_STONE|nh.BL_MASK_SLIME|nh.BL_MASK_STRNGL|nh.BL_MASK_FOODPOIS|nh.BL_MASK_TERMILL)
    return Player(turn=b.time,experience_level=b.experience_level,hp=b.hitpoints,max_hp=b.max_hitpoints,
        energy=b.energy,burden=b.carrying_capacity,hungry=b.hunger_state>=Hunger.HUNGRY,
        weak_or_worse=b.hunger_state>=Hunger.WEAK,blind=bool(prop.blind),
        confused=bool(prop.confusion),stunned=bool(prop.stun),hallucinating=bool(prop.hallu),
        polymorphed=bool(prop.polymorph),deadly_status=bool(deadly),
        hostile_distance=min((m[0] for m in hostile),default=None),safe_prayer_due=False)


def observed_spells(agent):
    ch=agent.character
    memory=getattr(ch,'spell_sustain_memory',{})
    turn=getattr(ch,'spell_sustain_menu_turn',-1)
    letters=getattr(ch,'known_spells',{})
    failures=getattr(ch,'spell_fail_chance',{})
    return {name:Spell(name,letters.get(name) or '',retention,failures.get(name,1.0),turn)
            for name,retention in memory.items()}


def utility_probe_due(agent):
    # Called only below inherited urgent healing, fatal-status and prayer checks,
    # and after rescue_priority returned control to known escapes.
    if agent.blstats.time<state(agent)['probe_until']:
        return False
    known=getattr(agent.character,'known_spells',{})
    if not any(known.get(n) for n in ('protection','cure blindness')):
        return False
    p=player(agent)
    return bool(not p.deadly_status and not p.polymorphed and not p.confused and not p.stunned
                and not p.weak_or_worse and p.burden<2
                and (p.blind or (p.hostile_distance is not None and p.hostile_distance<=2)))


def try_utility(agent):
    st=state(agent)
    st['probe_until']=agent.blstats.time+3
    agent.character.parse_spellcast_view()
    chosen=utility_spell(observed_spells(agent),player(agent),st['attempts'])
    if chosen is None:
        return
    letter=agent.character.known_spells[chosen]
    st['attempts'][chosen]=agent.blstats.time  # survives refusals and callback interruption
    refused=agent._CAST_REFUSED

    def keys():
        if refused.search(agent.message):
            return
        popup='\n'.join(agent.popup)
        # Never send an old spell letter to a missing or changed cast menu.
        if not re.search(r'^'+re.escape(letter)+r' -\s*'+re.escape(chosen)+r'\s',popup,re.M):
            return
        yield letter
        # Both added utilities are NODIR. Extra spaces here would be game actions.

    with agent.atom_operation():
        agent.step(A.Command.CAST,keys())
    agent.log('SPELL_SUSTAIN utility attempted: '+chosen)


def keep_books(agent,items):
    """Retain at most two positively known useful noncursed books."""
    ch=agent.character
    if ch.role not in (ch.HEALER,ch.WIZARD,ch.MONK,ch.PRIEST):
        return []
    result=[]
    seen=set()
    for item in items:
        if (item.category!=nh.SPBOOK_CLASS or not item.is_unambiguous()
                or item.status not in (Item.BLESSED,Item.UNCURSED)
                or item.shop_status!=Item.NOT_SHOP):
            continue
        name=item.object.name
        if name in USEFUL and name not in seen:
            seen.add(name);result.append(item)
    return sorted(result,key=lambda i:(i.object.name not in ('force bolt','healing'),i.unit_weight()))[:2]


def describe_book(item):
    return Book(name=item.object.name,level=item.object.level,
        status='blessed' if item.status==Item.BLESSED else 'uncursed',
        unambiguous=True,carried=True,in_shop=item.shop_status!=Item.NOT_SHOP,
        dull='dull spellbook' in item.text.lower())


def safe_study_context(agent):
    p=player(agent)
    # Sleep-resistance is not presently part of the adapter's verified contract;
    # dull books are conservatively declined below. Do not inspect internals.
    return (p.hostile_distance is None and p.hp*10>=p.max_hp*9 and not p.hungry
            and not any((p.blind,p.confused,p.stunned,p.hallucinating,p.polymorphed,p.deadly_status))
            and p.burden<2)


@Strategy.wrap
def upkeep(inventory):
    agent=inventory.agent
    st=state(agent)
    books=keep_books(agent,list(inventory.items))
    if not books or agent.blstats.time<st['upkeep_until'] or not safe_study_context(agent):
        yield False
        return
    yield True
    st['upkeep_until']=agent.blstats.time+200
    agent.character.parse_spellcast_view()
    spells=observed_spells(agent)
    p=player(agent)
    # Require deterministic uncursed study without relying on worn lenses.
    book=next((item for item in books if item.object.name in spells and
        refresh_eligible(describe_book(item),spells[item.object.name],p,
            intelligence=agent.blstats.intelligence,wearing_lenses=False,
            sleep_resistant=False,last_attempt_turn=-1000)),None)
    if book is None:
        return
    name=book.object.name
    letter=inventory.items.get_letter(book)
    study=Study(name,agent.blstats.time,spells[name].retention_percent)
    st['study']=study
    history_start=len(agent._message_history)

    def keys():
        if 'What do you want to read?' not in agent.single_message:
            return
        yield letter
        text=agent.single_message
        if 'difficult to comprehend' in text:
            yield 'n'  # contrary observed context: never take an unexpected study gamble

    try:
        with agent.atom_operation():
            agent.step(A.Command.READ,keys())
        messages=' | '.join(agent._message_history[history_start:])
        study.observe(messages,turn=agent.blstats.time)
        began=('begin to memorize the runes' in messages or 'continue your efforts to memorize' in messages)
        if not began and not study.completion_message_seen:
            return  # refused/cancelled READ must never become sixty idle turns
        for _ in range(60):
            messages=' | '.join(agent._message_history[history_start:])
            study.observe(messages,turn=agent.blstats.time)
            if study.completion_message_seen:
                agent.character.parse_spellcast_view()
                observed=observed_spells(agent).get(name)
                study.observe('',turn=agent.blstats.time,
                    current_retention=observed.retention_percent if observed else None,
                    menu_turn=observed.menu_turn if observed else None)
                break
            if study.result.value!='pending' or not safe_study_context(agent):
                break
            if agent.blstats.time-study.started_turn>=60:
                break
            agent.step(A.MiscDirection.WAIT)
    finally:
        # Propagate every preemption/error. Unknown completion stays unknown.
        study.interrupted()
        agent.log('SPELL_SUSTAIN study '+name+': '+study.result.value)

"""Undeployed policy prototype for PublicObservedSupplies.

Named ownership comes from observed NetHack shop greetings, not a moving @ glyph.
This module is not in any evaluated tree. Adapter evidence must be wired and
validated before these decisions can be used in a game.
"""
from dataclasses import dataclass
import re


def greeting_owner(message, shop_names):
    """Return one unambiguous observed (owner, shop type), else None.

    shk.c u_entered_shop emits Welcome[ again] to NAME's TYPE! or, for
    deaf/mute cases, You enter NAME's TYPE[ again]!. Possessives ending in s
    can use a bare apostrophe. Never infer ownership from plain map geometry.
    """
    kinds = '|'.join(re.escape(x) for x in sorted(set(shop_names), key=len, reverse=True)
                     if x != 'UNKNOWN')
    if not kinds:
        return None
    pattern = re.compile(r'(?:Welcome(?: again)? to |You enter )'
                         r"([^!\n\r]+?)(?:'s|') (" + kinds + r')(?: again)?!')
    matches = {(m.group(1).strip(), m.group(2)) for m in pattern.finditer(message or '')}
    if len(matches) != 1:
        return None
    owner, kind = next(iter(matches))
    if not owner or len(owner) > 80:
        return None
    return owner, kind


@dataclass(frozen=True)
class OwnerIntent:
    level_key: tuple
    shop_id: int
    owner_name: str
    created_command: int


@dataclass(frozen=True)
class PaymentEvidence:
    level_key_before: tuple
    level_key_after: tuple
    shop_id_before: int
    shop_id_after: int
    observed_payee_name: str
    owner_binding_unique: bool
    command_serial: int
    reply_command_serial: int
    reply: str
    unpaid_items_after: int
    hallucinating: bool = False
    observation_ambiguous: bool = False


def confirmed_settlement(intent, proof):
    """A foreign, stale or ambiguous zero-debt answer must preserve intent.

    The anonymous 'don't owe any money here' reply is insufficient for this
    prototype. Passing means only that the supplied evidence meets the policy;
    the adapter must actually observe/bind it, never manufacture missing fields.
    """
    if not intent.owner_name or not proof.owner_binding_unique or proof.hallucinating or \
            proof.observation_ambiguous or proof.unpaid_items_after != 0:
        return False
    if proof.level_key_before != intent.level_key or proof.level_key_after != intent.level_key or \
            proof.shop_id_before != intent.shop_id or proof.shop_id_after != intent.shop_id:
        return False
    if proof.observed_payee_name != intent.owner_name or \
            proof.command_serial <= intent.created_command or \
            proof.reply_command_serial != proof.command_serial:
        return False
    return bool(re.search(r'(?:^|[.!?]\s+)You do not owe ' + re.escape(intent.owner_name) +
                          r' anything\.', proof.reply or ''))

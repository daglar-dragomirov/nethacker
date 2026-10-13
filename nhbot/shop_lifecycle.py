"""Observed purchase/debt lifecycle; adapted from Luab b16051f with named-owner proof.

Ordinary food consumption uses owned food; emergency callers keep the inherited
eat/quaff behavior, recording unpaid consumption before inventory can disappear.
"""
from dataclasses import dataclass

import numpy as np
import nle.nethack as nh
from nle.nethack import actions as A

from .glyph import G, Hunger
from .item.item import Item
from .item.utils import flatten_items
from .named_shop_keeper_adapter import observe_named_keeper, pay_target_from_observation
from .observed_shop_owner_policy import OwnerIntent, PaymentEvidence, confirmed_settlement
from .strategy import Strategy


@dataclass
class ShopTransaction:
    level_key: tuple
    shop_id: int
    origin: tuple
    owner_name: str = None
    created_payment: int = 0
    retry_after: int = 0
    consumed_unpaid: bool = False
    returned_goods: bool = False


def quantity_price(item, count=1):
    if count < 1 or count > item.count or item.price <= 0:
        return None
    return (int(item.price) * count + int(item.count) - 1) // int(item.count)


class ShopLifecycle:
    def _shop_state_init(self):
        if not hasattr(self, '_shop_transaction'):
            self._shop_transaction = None
            self._shop_settling = False
            self._shop_payment_serial = 0
            self._shop_payment_confirmed = False
            self._shop_unknown_consumption = False

    def _unpaid_items(self):
        return [i for i in flatten_items(self.items) if i.shop_status == Item.UNPAID]

    def shop_debt_pending(self):
        self._shop_state_init()
        return self._shop_transaction is not None or self._shop_unknown_consumption or bool(self._unpaid_items())

    def _transaction_shop(self):
        self._shop_state_init()
        t = self._shop_transaction
        level = self.agent.current_level()
        if t is None or level.key() != t.level_key:
            return None
        return level.shops.records.get(t.shop_id)

    def _remember_unpaid(self):
        self._shop_state_init()
        if self._shop_transaction is None and self._unpaid_items():
            level, b = self.agent.current_level(), self.agent.blstats
            shop = level.shops.shop_at(b.y, b.x, include_entrance=True)
            if shop is not None:
                self._shop_transaction = ShopTransaction(level.key(), shop.shop_id, (b.y, b.x),
                    getattr(shop, 'owner_name', None), self._shop_payment_serial)

    def record_shop_consumption(self, item):
        """Record before inherited lifesaving eat/quaff can remove the item."""
        if item.shop_status == Item.NOT_SHOP:
            return
        self._remember_unpaid()
        t = self._shop_transaction
        shop = self._transaction_shop()
        b = self.agent.blstats
        if t is None or shop is None or not shop.interior[b.y, b.x]:
            self._shop_unknown_consumption = True
        if t is not None:
            t.consumed_unpaid = True
            t.returned_goods = False

    def shop_exit_blocked(self, from_y, from_x, to_y, to_x):
        shop = self._transaction_shop()
        if shop is None:
            return False
        t = self._shop_transaction
        # A verified return of all carried merchandise permits ordinary exit,
        # without declaring an unobserved consumed bill settled. Buying again is
        # still blocked until a named zero-debt PAY reply clears the intent.
        if t.returned_goods and not t.consumed_unpaid and not self._unpaid_items():
            return False
        inside = lambda y, x: shop.interior[y, x] or (y, x) in shop.entrances
        return bool(inside(from_y, from_x) and not inside(to_y, to_x))

    def shop_emergency(self):
        a, b = self.agent, self.agent.blstats
        p = a.character.prop
        conditions = int(a.last_observation['blstats'][nh.NLE_BL_CONDITION])
        deadly = conditions & (nh.BL_MASK_STONE | nh.BL_MASK_SLIME | nh.BL_MASK_STRNGL |
                               nh.BL_MASK_FOODPOIS | nh.BL_MASK_TERMILL)
        return bool(a.get_visible_monsters() or b.hitpoints * 2 < b.max_hitpoints or
                    b.hunger_state >= Hunger.FAINTING or p.polymorph or p.blind or p.hallu or
                    p.confusion or p.stun or deadly)

    def _pay_shop_bill(self):
        self._shop_state_init()
        self._shop_payment_confirmed = False
        t, shop = self._shop_transaction, self._transaction_shop()
        if t is None or shop is None or not t.owner_name:
            return ''
        a = self.agent
        observed = observe_named_keeper(a, shop, t.owner_name, G.SHOPKEEPER)
        if observed is None:
            return ''
        before_level, before_shop = a.current_level().key(), shop.shop_id
        self._shop_payment_serial += 1
        serial = self._shop_payment_serial

        def answers():
            for _ in range(100):
                message = a.single_message
                if 'Pay whom?' in message:
                    target = pay_target_from_observation(a, shop, observed, G.SHOPKEEPER)
                    if target is None:
                        yield A.Command.ESC
                        return
                    directions = {(-1, -1): 'y', (-1, 0): 'k', (-1, 1): 'u',
                                  (0, -1): 'h', (0, 1): 'l',
                                  (1, -1): 'b', (1, 0): 'j', (1, 1): 'n'}
                    for _ in range(sum(a.glyphs.shape)):
                        y, x = a.cursor_pos
                        if (y, x) == target:
                            yield '.'
                            break
                        yield directions[(int(np.sign(target[0] - y)), int(np.sign(target[1] - x)))]
                    else:
                        yield A.Command.ESC
                        return
                elif 'Itemized billing?' in message:
                    yield 'n'
                elif 'Pay?' in message:
                    yield 'y'
                elif a._observation['misc'][2]:
                    yield A.MiscAction.MORE
                else:
                    return

        a.step(A.Command.PAY, answers())
        reply = a.message
        self.items.update(force=True)
        after = a.current_level().shops.shop_at(a.blstats.y, a.blstats.x)
        evidence = PaymentEvidence(before_level, a.current_level().key(), before_shop,
            after.shop_id if after is not None else -1, observed.owner_name, True,
            serial, serial, reply, len(self._unpaid_items()),
            bool(a.character.prop.hallu), bool(getattr(shop, 'owner_ambiguous', False)))
        intent = OwnerIntent(t.level_key, t.shop_id, t.owner_name, t.created_payment)
        self._shop_payment_confirmed = confirmed_settlement(intent, evidence)
        return reply

    def pay_or_drop_unpaid(self):
        self._remember_unpaid()
        t, shop = self._shop_transaction, self._transaction_shop()
        if t is None or shop is None or self._shop_settling:
            return
        a, b = self.agent, self.agent.blstats
        # Do not force an emergency escape back into its original shop.
        if not shop.interior[b.y, b.x]:
            return
        self._shop_settling = True
        try:
            with a.atom_operation():
                t.retry_after = b.time + 10
                self._pay_shop_bill()
                b = a.blstats
                if a.current_level().key() != t.level_key or not shop.interior[b.y, b.x]:
                    return
                unpaid = self._unpaid_items()
                returnable = [i for i in unpaid if i in self.items.all_items and i.can_be_dropped_from_inventory()]
                if returnable:
                    self.drop(returnable, smart=False)
                    self.items.update(force=True)
                    b = a.blstats
                    if a.current_level().key() != t.level_key or not shop.interior[b.y, b.x]:
                        return
                    if not self._unpaid_items() and not t.consumed_unpaid:
                        t.returned_goods = True
                if not self._unpaid_items():
                    if not self._shop_payment_confirmed:
                        self._pay_shop_bill()
                    if self._shop_payment_confirmed and not self._unpaid_items():
                        self._shop_transaction = None
                        a.log('SHOP named-owner bill settled')
        finally:
            self._shop_settling = False

    @Strategy.wrap
    def settle_shop_debt(self):
        self._remember_unpaid()
        t, shop = self._shop_transaction, self._transaction_shop()
        a, b = self.agent, self.agent.blstats
        if t is None or shop is None or self._shop_settling or self.shop_emergency() or \
                not shop.interior[b.y, b.x] or \
                (t.returned_goods and not t.consumed_unpaid and not self._unpaid_items()):
            yield False
            return
        yield True
        before = a.blstats.time
        if before >= t.retry_after:
            self.pay_or_drop_unpaid()
        # No free-command or cyclic-preempt loop while waiting for the owner.
        if self._shop_transaction is not None and a.blstats.time == before and not self.shop_emergency():
            a.step(A.MiscDirection.WAIT)

    def begin_shop_purchase(self, shop, identity_key):
        """Resolve a fresh owner before pickup; failure cools down this target."""
        self._shop_state_init()
        observed = observe_named_keeper(self.agent, shop, getattr(shop, 'owner_name', None), G.SHOPKEEPER)
        if observed is None:
            self._buy_food_blocked[identity_key] = (3, self.agent.blstats.time + 200)
            return False
        level, b = self.agent.current_level(), self.agent.blstats
        self._shop_transaction = ShopTransaction(level.key(), shop.shop_id, (b.y, b.x),
                                                observed.owner_name, self._shop_payment_serial)
        return True

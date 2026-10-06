"""Source-defined selector for the existing generic HP healing branch."""
def choose_healing_buc(items, carried, hp, maximum_hp):
    chosen = items[0]
    # Do not reconstruct or change the old container retrieval plan.
    direct = {id(item) for item in carried}
    if (id(chosen) not in direct or chosen.status not in (1, 2, 3)
            or getattr(chosen, 'shop_status', 0) != 0):
        return chosen
    name = chosen.object.name
    if name not in ('healing', 'extra healing'):
        return chosen
    # potion.c: known BUC gives 4, 6 or 8 dice, with positive sides.
    # Higher BUC adds positive dice of the same kind, hence dominates every
    # HP threshold. Preserve the first item if its minimum already fills HP.
    deficit = maximum_hp - hp
    for item in items:
        if (id(item) in direct and item.object.name == name
                and getattr(item, 'shop_status', 0) == 0
                and item.status in (1, 2, 3) and item.status > chosen.status
                and deficit > 2 + 2 * chosen.status):
            chosen = item
    return chosen

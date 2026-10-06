"""Conservative innate HP-immunity guard for identified fire/cold rays."""

def innate_ray_hp_immunity(item, monster):
    objects = getattr(item, 'objs', ())
    if len(objects) != 1:
        return False
    name = getattr(objects[0], 'name', None)
    mask = {'fire': 0x01, 'cold': 0x02}.get(name)
    if mask is None:
        return False
    return bool(getattr(monster, 'mresists', 0) & mask)

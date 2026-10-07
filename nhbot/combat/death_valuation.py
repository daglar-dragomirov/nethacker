"""Visible death-type immunity valuation; normalize the actual NLE char binding."""
def visible_death_type_immunity(item, monster, agent):
    objects=getattr(item,'objs',())
    if len(objects)!=1 or getattr(objects[0],'name',None)!='death':return False
    prop=getattr(getattr(agent,'character',None),'prop',None)
    if getattr(prop,'hallu',True):return False
    flags=getattr(monster,'mflags2',0)
    symbol=getattr(monster,'mlet',None)
    if isinstance(symbol,str):symbol=ord(symbol) if len(symbol)==1 else None
    return bool(flags & (2|256)) or symbol in (22,55) or getattr(monster,'mname',None) in ('manes','Death')

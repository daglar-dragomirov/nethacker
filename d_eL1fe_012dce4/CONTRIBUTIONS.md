# Role router (eL1fe)

Every game is played by one complete bot written by others, chosen by the character's role; all
credit for those engines belongs to their authors (see `influences`). Ours are the router, the
routing table below (measured on eL1fe's held-out multi-role benchmark: paired games, fresh seeds)
and the fixes listed at the end.

Default engine: `dag69` (github.com/daglar-dragomirov/nethacker@69baf4943e2f47a23715b3814438b180c3c64b75:
vkurenkov's jawfish 21e6539 with the castle crossing, plus daglar's additions)

- Healer/gnome: `dagfc5` (github.com/daglar-dragomirov/nethacker@fc50360e721e98e5a322dbd6282c703718bd4d46)
- Samurai: `jawfish` (github.com/vkurenkov/nethacker@f15bb8c8e01d905d1946e32bfd2558e17394eab6)
- Tourist: `kefirski` (github.com/kefirski/nethacker@314507ee72fcedf3749b6e2b4d60330bc159e88f)

## eL1fe's fixes in the engines

Every engine:

- never wield darts, shuriken, boomerangs, arrows or bolts for melee: a Tourist bashed with its +2
  darts and never threw one

`dag69` (every role not listed above):

- healing spells: AutoAscend never parsed the spell list, so no role ever cast healing; now a Healer,
  or a Monk or Wizard that knows healing, casts it at low HP
- Wizards cast force bolt, their starting attack spell, on a clear line (the fight heuristic only
  meleed; ported from CleverShovel 0d1fb22), never into a shop or shop stock: the bolt flies on
  past its target and breaks potions
- `cast()` answered "In what direction?" with calc_direction's string: 'ne' is two keys and 'n' is
  the vi-key for south-east, so every directional cast went wrong; it now sends the compass action
- no casting while Stressed ("Your concentration falters while carrying so much stuff", a lost turn)
- a known scroll of magic mapping is read from Dlvl 3 when no stairs down are known
- Sokoban desync, phantom altars, dragon-scale parsing, cockatrice touch guard, stoning cure,
  no shop-door kicks, trees unwalkable

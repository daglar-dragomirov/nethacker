# Role router (eL1fe)

Every game is played by one complete bot written by others, chosen by the character's role; all
credit for those engines belongs to their authors (see `influences`). Ours are the router, the
routing table below (measured on eL1fe's held-out multi-role benchmark: paired games, fresh seeds)
and the fixes listed at the end.

Default engine: `dag25` (github.com/daglar-dragomirov/nethacker@e29eb8281b13784716d9121e4f01ec60c2bb2165: the base engine of daglar's e29eb82,
vkurenkov's jawfish s25 238c254 plus daglar's additions), with every eL1fe fix below ported onto it

- Wizard: `dage29` (github.com/daglar-dragomirov/nethacker@e29eb8281b13784716d9121e4f01ec60c2bb2165, its base engine
  unchanged): its Wizards never cast force bolt in combat and grind on Dlvl 1; against `dag25` with our force bolt,
  +3.1 points over 240 paired Wizard games on five identities (and +7.2 on the verified board)
- Healer (human): `vlom8b4` (github.com/vlomshakov/nethacker@8b492ce95e6988b0eae2de84aef1379f885a1306), +3.7 points over 96 paired
  human Healer games against the previous router
- Healer/gnome: `dagfc5` (github.com/daglar-dragomirov/nethacker@fc50360e721e98e5a322dbd6282c703718bd4d46)
- Samurai: `jawfish` (github.com/vkurenkov/nethacker@f15bb8c8e01d905d1946e32bfd2558e17394eab6)
- Tourist: `kefirski` (github.com/kefirski/nethacker@314507ee72fcedf3749b6e2b4d60330bc159e88f)

## eL1fe's fixes in the router

- the role is read from the Xp 1 rank title in the status line ("Agent the Rambler") when the welcome
  line is missing (a full or new moon message can replace it), instead of falling back to the default
  engine

## eL1fe's fixes in the engines

Every engine:

- never wield darts, shuriken, boomerangs, arrows or bolts for melee: a Tourist bashed with its +2
  darts and never threw one

`dag25` (every role not listed above; the Wizard items below no longer play, Wizards are routed to `dage29`):

- healing spells: AutoAscend never parsed the spell list, so no role ever cast healing; now a Healer,
  or a Monk or Wizard that knows healing, casts it at low HP
- Wizards cast force bolt, their starting attack spell, on a clear line (the fight heuristic only
  meleed; ported from CleverShovel 0d1fb22), never into a shop or shop stock: the bolt flies on
  past its target and breaks potions
- `cast()` answered "In what direction?" with calc_direction's string: 'ne' is two keys and 'n' is
  the vi-key for south-east, so every directional cast went wrong; it now sends the compass action
- no casting while Stressed ("Your concentration falters while carrying so much stuff", a lost turn)
- a known scroll of magic mapping is read from Dlvl 3 when no stairs down are known
- a known scroll of teleportation is read as a last resort (the engine read every unknown scroll when about
  to die, but never an identified teleportation: 12 of 48 dead elven Wizards carried one)
- force bolt never flies on into a pet or a peaceful standing behind the target (a Wizard's bolt killed a
  jackal and hit its own housecat, which turned on it)
- Wizards keep off metal body armor, metal gloves and heavy shields, which push force bolt to 60-80% failure
  (found by our `nethackers evolve` run)
- the weak-role Dlvl-1 grind of the s25 line kept for Rogues only (Wizards with force bolt lose -12.6 on Dlvl 1);
  daglar (2f207d4) found jawfish's XL 5-6 Dlvl-3 grind killing the weak roles;
  measured per role on this engine, it holds for Rogues (+3.3 and +4.1 on two identities, 48 paired games
  each) and not for Wizards, Priests, Valkyries or Barbarians
- Archeologists dig down out of a shop they fell into, through an empty floor square when nothing is owed:
  the shopkeeper blocks the door for a pick-axe carrier and digging in shops was forbidden, so dig-diving
  Archeologists starved in there (found by our `nethackers evolve` run; +6.0, +5.3, +2.9, +1.0 points on four
  Archeologist identities, paired fresh seeds)
- no role throws or fires where its pet may be standing out of sight: a dagger thrown past a kitten that had
  stepped into a dark corridor killed it (-15 alignment, -5 Luck), and every prayer failed after that (found by
  our `nethackers evolve` run for Valkyries; extended to Rogues and Rangers)
- Knights never melee a floating eye they can see: its passive gaze froze them for ~100 turns, 3 of 10 early
  Knight deaths on the judge's seeds (found by our `nethackers evolve` run)
- Barbarians count A-class lawful minions (couatl, Aleax, Angel...) as ignoring Elbereth: a dig-diving Barbarian
  engraved and dug on beside one until 5 HP (found by our `nethackers evolve` run)
- Sokoban desync, phantom altars, dragon-scale parsing, cockatrice touch guard, stoning cure,
  no shop-door kicks, trees unwalkable

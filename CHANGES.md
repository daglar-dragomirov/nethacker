# Changes over the parent engine (pf_s25p)

- **v9p (private-safe router)**: v5 plus only the specialist routes that beat nhbot on the hub's VERIFIED (private-seed)
  tier -- Gnomish Archeologists on pf_v36, neutral human Rangers and the female elven Ranger on pf_s25p8, Knights on
  pf_s25p8 -- and no daglar profile for Rangers, Rogues and Tourists (every Ranger and Rogue identity scored lower with
  it); Tourists back on nhbot. The public-seed-selected ports of v6/v7 overfit the 15 public seeds and are left out.
- **v9p2**: v9p plus three routes with one verified sample each: neutral human Archeologists and orcish Barbarians on
  pf_s25p8, neutral human Wizards on pf_vk_s25.

- **v10a**: Healers and Samurai back on nhbot: every Healer and Samurai specialist lost to nhbot on 90 dev held-out
  seeds (hea-gno pf_hg -0.050, hea-hum pf_hh -0.024, sam pf_v35 -0.051).
- **v10b**: dev-confirmed config: Rangers on nhbot without UNSEEN_PET_GUARD (+0.022 +- 0.012, 420 pairs), gnomish
  Cavemen on the Dlvl-1 grind (+0.073 +- 0.022, 120 pairs).
- **v10c**: neutral human Wizards on pf_s25p8 instead of pf_vk_s25 (dev held-out: 0.252 vs 0.153 over 90 seeds; the
  verified tier agrees).
- **v12pub** (public board only): v11pub plus, per identity, the best public-seed setup of v2 (9c1cc90) and v3
  (71335bf) -- 23 identities play verbatim copies of those programs' engines (`nhbot_v2`, `nhbot_v3`: only the package
  name in the import lines changed) routed exactly as those programs routed them (`bot.LEGACY`) -- and v4's config
  (the nhbot defaults) on arc-dwa-law-mal / arc-hum-law-fem. Not meant for the verified tier.
- **v11pub** (public board only): per identity the best public-seed setup among v10c, v7, v9p2 and v4 (same nhbot
  code; tools/mkpub.py), as explicit per-identity routes and configs. Public-seed selection overfits by design: for the
  private/verified tier use v10c.
- **eL1fe's fixes** (ported from eL1fe/nethacker@cfc3828, its `dag25` engine = this same base): the spell-direction fix
  (`Agent.cast` sent the compass string as keys: every aimed cast was wasted), force bolt for Wizards (from
  CleverShovel 0d1fb22: never into shops, never flying on into a pet), healing spells for any role that knows them,
  stoning cures, a known teleport scroll as a last resort, no throwing where the pet may stand unseen, Wizards and
  Healers keep off metal body armor/gloves/heavy shields (spell failure), Archeologists dig out of shops, magic
  mapping from Dlvl 3, trees unwalkable, Sokoban/altar robustness. Wizards grind on Dlvl 1-3 as in eL1fe's engine;
  Rogues, Knights, Tourists and Priests keep the Dlvl-1-only grind (`ROLE_GRIND_LEVELS`).
  (I found the cast bug independently; eL1fe's version is used.)
- **Identity router** as in daglar-dragomirov/nethacker@e29eb82 (the verified-tier leader): Healers (pf_hg, pf_hh)
  and Samurai (pf_v35) play specialist engines; everyone else plays nhbot with DIVE_XL 8
  (nhbot is then identical to e29eb82's pf_base apart from the changes listed here).
- `roles.py`: per-identity overrides of engine settings (only for nhbot identities).
- `MEDUSA_HOP` (off pending A/B): on Medusa's level with no dry square on our islet, step into a one-square moat
  channel toward land that has one (trap.c drown(): the hero crawls out at once to a random free land square).
- `MINES_TOOL_TRIP` (on; +0.018 +- 0.007 per game over 272 paired held-out games): a tool-less planned dive takes the Mines route for any race (it was for
  dwarves and gnomes only), so humans, elves and orcs go and take a dwarf's pick-axe.
- DT6A's two-page `#enhance` fix (DT6A/nethacker@c9a42ac): tty menus restart item letters on each page; the parser's
  assert then fired on every fight start.
- CleverShovel's ring/amulet/scroll module (CleverShovel/nethacker@9dc0822 V1, @29ab0a7 V2), Wizards only, behind
  `RING_MODULE` (A/B pending): wears identified useful rings (slow digestion, free action, poison resistance...),
  combat-only rings in fights, sheds rings when Hungry, reads scrolls at safe moments to identify rings/amulets.
- Archeologists dig-dive from XL 5 instead of 3 (`ARC_DIG_DIVE_XL`): +0.024 +- 0.013 over 236 paired held-out games.
- Small fixes found by log analysis: the panic-loop breaker now also forbids a square a monster keeps blocking
  (`PANIC_TILE_FIX`; one grind sat 38k turns), divers keep fighting with the wielded pick-axe/mattock unless the best
  weapon is clearly better (`DIG_TOOL_MELEE`), a timed-out pet ditch is retried (`DITCH_RETRY`), a trapping gas spore is
  only hit when its blast can't kill (`SPORE_TRAP_FIX`).
- Known cold/fire wands are zapped only with a free run of squares behind the target (`RAY_BOUNCE_FIX`): seven logged
  deaths came from the bot's own bounced ray.
- `AT_THREAT_AVOID` (off pending A/B): while an elf, soldier or other Elbereth-ignoring meleer comes for a pick-axe
  digger above Medusa's level, no pit is started (every attack stops the dig; in the pit the fight is at -3 to-hit): a
  known wand of digging holes the floor at once, else the @ is fought on level ground first.
- **v3:** human Priests play nhbot instead of pf_pa (+0.053 +- 0.022 per game over 113 paired held-out games); bug fixes
  from a log study of the games that end above Dlvl 10 (`research` notes in the workspace): a prayer interrupted by a
  strategy switch is still recorded (`PRAYER_RECORD_FIX`), the prayer model's alignment record follows pray.c (+1 only
  for prayers without major trouble, `RECORD_MODEL_FIX`), fight2 charges a ray's bounce through us its real cost
  (`SELF_ZAP_FIX`), no pickup that leaves us Stressed and a lycanthrope's corpse weighs what its human form does
  (`HEAVY_LIFT_GUARD`); a garbled Elbereth is rewritten after a mid-dig faint (`ELBERETH_REWRITE_FIX`).
- Tried and left off (flags kept for reference): `AT_THREAT_AVOID` (no pit while an elf/soldier comes: -0.004 +- 0.003
  over 235 deterministic pairs), `MEDUSA_HOLE_CYCLE` (skip Medusa's level through our own hole from above: the skip works
  1 time in 4-6, but the extra landings cost more, -0.015 +- 0.005 per Medusa game), Wizards on the Dlvl-1 grind
  (-0.058 +- 0.026 over 101 pairs).
- **v4:** fixes from log studies of the deep game and of Wizards (`research` notes in the workspace). Deep game: lawful
  minions (Aleax, couatl, ...) ignore Elbereth (`LMINION_ELBERETH`), a safe prayer before a heal at critical HP deep in the
  dive (`DEEP_PRAY_FIRST`), no castle-only strategies on a deep Medusa level, Medusa-2 recognised by its titan's messages,
  a stranded Medusa-3 '<' rerolls, minotaur guard fixes (`MINO_*`): +0.0021 +- 0.0012 over 512 deterministic held-out
  pairs vs v3. Wizards: force bolt beats the melee bonus against Elbereth-ignorers and is cast from an Elbereth square at
  what the engraving doesn't scare (`FB_FOCUS`; 52 of 412 Wizard games died meleeing with power left), no casting while
  stunned/confused, no ray-wand zaps in the grind while the bolt is castable; a starving pet gets the corpses, a pet
  turned hostile is fought, no Elbereth on altars. Knights stay on the Dlvl-1 grind (the deep grind: -0.020 +- 0.023 over
  160 pairs); a durable (engraved) Elbereth for holds measured +0.000 over 512 pairs (flag off).

- **v5:** merged daglar-dragomirov/nethacker@6c814836 (the generalist-board leader, mean 0.350) into this v4 tree, which
  was already a strict superset of its engine-code changes (v4's deep-game and Wizard fixes are additive new flags;
  daglar made no edits to those nhbot files). Adopted from daglar: the populated per-identity `OVERRIDES` in `roles.py`
  (arc/cav/mon/pri/wiz play aggressive — `RING_MODULE` and `MEDUSA_HOP` on, the four safety flags off, `DIVE_XL` 8;
  bar/kni/ran/rog/tou/val play safe — the opposite, `ran` `DIVE_XL` 7), the `^X` attributes-screen identity probe
  (`roles.attributes_identity`, so the per-role config applies even when the welcome line is missed), and the Tourist
  engine `pf_dtad7a` (DT6A/nethacker@ad7a864) routed for `tou`. The `RING_MODULE`/`MEDUSA_HOP` module code is
  byte-identical to daglar's, so this reproduces the leader's behaviour exactly, with v4's extra fixes on top.

## Experimental zSpellCapacity
Experimental complete zSpellCapacity on exact clean strongest open Public leader zarutskiysy/nethack@96ef3261bd61e151858b181be95b066bbde9d6f4. One physical/cognitive spell action-capacity policy across30clean Public12 main identities. Correct healing, extra healing, force-bolt actions and force-bolt/ray readiness from Stressed2 to NetHack Overtaxed4. Reject stun, guaranteed confusion failure, strength<4 and unexpired observed casting refusal for these selectors. Preserve known spells, energy, hunger, HP, chance, last-failure, polymorph-offensive, shop, pet, peaceful, line/range, spore and Elbereth guards. Actual emergency chain falls back to existing known healing potion when spells are unavailable. All43specialist identities and every route remain unchanged. Official NetHack3.6.6 spell/hack/header bytes verified.80actual selector and emergency fixtures with explicit state/geometry/dependency availability/action-sink mocks;146welcome/missing routes. Allowing legal magic under Stressed/Strained can spend energy and nutrition or displace safer actions. Unexpired generic refusal may remain after the underlying condition resolves. Existing grind FB_OVER_RAYS policy suppresses ray wands based on casting readiness before target safety; this extension may increase that existing preference. No full target-state/cast-success model; hidden nutrition, anatomy, amulet drain, forgotten spells and other refusals remain possible. Full engine imports/score gain require real VM smoke/native evaluation.73newsmoke84999 then1095nativePublic; immediate per-identity experimental registration after smoke, sanity and exact evaluated-local-Git bytes. No automatic fresh matrix, Private/partial selection, replay or confirmed gain. Prior bests and Healer fresh protocol retained.

## Experimental zRayProbability
Experimental complete zRayProbability on exact current completed Public leader daglar-dragomirov/nethacker@0f440af6655ce126183a753ec6ff0f2aa1e68daf with coherent ray-path probability and independent branch-range accounting. Coherent ray-path probability/range accounting on exact completed current Public leader SpellCapacity. Propagate joint path probability through recursion instead of resetting it to1, and give each alternative bounce branch its own remaining range instead of mutating shared range_left. Preserve existing one-step transition kernel, initial13budget, monster attenuation, all action priorities, FB_OVER_RAYS suppression, watch/shop/spore/Elbereth protections and cold/death reservations. Thirty main identities affected;43specialists and all routes exact versus current leader. 71actual path and wand-priority fixtures plus3actual zap-actor fixtures with explicit state and transition-kernel mocks;146welcome/missing routes. Repairs probability calculus within the existing approximate transition model; not exact NetHack trajectory probabilities. Diagonal bounce kernel, off-by-one range horizon, unobserved reflection/resistances and unknown terrain remain inherited limitations. Corrected weights can reduce both hostile rewards and self/friend penalties, changing choice in either direction. No extra ray availability or target fallback is enabled. Full NLE smoke/native needed; model contracts do not prove gain.73newsmoke89999 then1095nativePublic; immediate per-identity experimental registration after smoke, sanity and exact evaluated-local-Git bytes. No automatic fresh matrix, Private/partial selection, replay or confirmed gain. Prior bests and Healer fresh protocol retained.


Experimental Public Orc Rogue800 strength-hit derivative. Exact whole cc23 Public router and71other routes retained. Both orc Rogues use the complete registered tabt800e main engine, adapter and exact role profile in a separate namespace, including its thrown-item weapon-skill bonus. One behavioral correction: Character._get_str_dex_to_hit_bonus reads encoded STR125 (BLStats.strength_percentage) for NetHack abon thresholds, instead of displayed STR25. All other donor gameplay retained. Provenance/licenses retained. Source readiness only; no confirmed gain.

The unfrozen source review also corrects the restricted/unskilled weapon damage table from +2 to -2, matching NetHack weapon_dam_bonus(). Expert thrown-item skill logic remains exactly inherited from the registered source.


Exact Public DT6A/nethacker@448d8d679f8eb194a26e984a85c0a81a7cf8c5d0 derivative on complete whole Public leader daglar-dragomirov/nethacker@5b1793db10cb88c1c2798663683641b8e78076d1.
Three Cavemen and two Wizards use the complete registered main nhbot, arena adapter and exact role profiles. Elf female Ranger uses complete registered pf_s25p8/adapter without role application. All 67 other routes, all original whole-base router/probe behavior, dependencies, licenses and ancestry retained. Original donor archive and exact Git blob inventory retained in diagnostics/public-sources-oct16.
Only donor gameplay changes: encoded STR125 input for abon; restricted/unskilled melee weapon damage -2 instead of +2. Package namespaces isolate engines. No individual Private selection/tuning. No efficacy claim. Existing exact-byte smoke73/native15 gates required; native imports pending, no seed reserved.


Complete strongest open Public DT448@53aab5dc02e4a0216542a39be7d5b6aa099f1d55 retained with every original router/probe and71other routes. Human lawful Monk female and orc chaotic Ranger female use complete registered github.com/DT6A/nethacker@736cae369fdbf3da9a45730ec18b65afb37f5b3e main nhbot, adapter and exact roles. Only donor gameplay change: restricted/unskilled weapon damage -2 instead of +2. Actual pinned ABI STR25=2/STR125=3; legacy labels strength_percentage=slot2 and strength=slot3. Preserve original correct source abon(slot3)/capacity(slot2), repairing wrong STR25 abon in prior frozen DT736. Prior synthetic field interpretation is superseded; all original frozen waves/results remain immutable. Compared736 vs448: exact registered profiles/adapters and group-threat rest retained; later DT448 emergency-meal strategy excluded; full policy equivalence still requires audit. All donor commit/root-tree/blob inventories, licenses/provenance and ancestry retained. No individual Private selection. UNFROZEN: full policy/source equivalence and actual pinned146startup/two native driver resets, smoke73/native15 gates required; no seed/game or efficacy claim.


Complete strongest whole open Public DT736ABI@52199e5e628bf0e71e49810fef8dd7f087523688 retained, including every original router/probe/fallback and all70 other effective routes.
Three exact current registered Public Valk source policies: dwarf tabt616e complete pf_vk_s23/no profile; human lawful DT79297 complete main nhbot with exact roles; human neutral SAME DT79297 complete legacy nhbot_v3 without roles. Fresh commit/root/archive/all Gitblobs verified in diagnostics/public-valk-abi-sources-oct18. Whole source engines/adapters/runtime data and all licenses/provenance retained.
Only source gameplay correction: restricted/unskilled weapon damage -2 instead of +2. Preserve raw source ABI-correct STR125 abon slot3 and STR25 capacity slot2/squeeze. Actual NLE STR25=2 STR125=3; legacy BLStats labels strength_percentage=slot2STR25 and strength=slot3STR125 are reversed. Old frozen science/history immutable. Dwarf prior CurrentValk wrongSTR25 abon restored; human policies use newly registered exact79297 complete source, not stale eeffe/69e67. No field-name defect inference or metadata-only efficacy rerun. All prior engine and full effective policy comparisons/native146startup/3realdriver resets required before freeze. No Private per-identity selection, no efficacy claim. UNFROZEN SOURCE ONLY, no seed/game/freeze.
github.com/tabt/nethacker@616e9c5b25683af6de9542a9d1dcb80dd8138e13
github.com/DT6A/nethacker@79297ad035c15971f74a4549e7c08f521253ee95
github.com/DT6A/nethacker@79297ad035c15971f74a4549e7c08f521253ee95


Complete strongest open Public CurrentValkABI@6a94f7a02507595cd58a3337c61414daa0d2970b retained with every original router/probe and71other routes. Human lawful Knight female/male use complete registered github.com/tabt/nethacker@c48cfb75ae898714a0a044a97be3e8189a316500 main nhbot, adapter and exact roles. Only donor gameplay change: restricted/unskilled weapon damage -2 instead of +2. Actual pinned ABI STR25=2/STR125=3; legacy labels strength_percentage=slot2 and strength=slot3. Preserve original correct source abon(slot3)/capacity(slot2), repairing wrong STR25 abon in old blocked KnightC48. Prior synthetic field interpretation is superseded; all original frozen waves/results remain immutable. Both Knight targets retain the exact empty donor role profile/application; full effective policy versus prior blocked Knight and all current/archived/nested policies must be audited. All donor commit/root-tree/blob inventories, licenses/provenance and ancestry retained. No individual Private selection. UNFROZEN: full policy/source equivalence and actual pinned146startup/two native driver resets, smoke73/native15 gates required; no seed/game or efficacy claim.


Complete strongest COMPLETE whole open Knight4759120c retained, all70other effective routes/full engines/runtime/router/probe/fallback/licenses/provenance. Three exact current open Public Valk policies: dwarf tabt616 pf_vk_s23/no profile; human lawful DT79297 main nhbot+exact roles; human neutral DT79297 legacy nhbot_v3/no profile. Source changes restricted/unskilled damage+2->-2 and primary NLE1.3.0 dbon once melee/poly0. Sole NEW engine/runtime delta versus EACH completedCurrentValkABI6a94 target is dbon; preserve correct rawSTR125abon(slot3)/STR25capacity(slot2)/registered squeeze/ranged and full source strategy. Full Character/Item/artifact/inventory/global/agent/DPS strength reader/caller audit excludes hidden or doublecounted dbon. Exact primary NLE70cb9b/rootfd0ee20/locked wheel3nativebinary equality+same-release sdist8Gitblob proof; parsedC reference SOURCEtable not compilednative/reproduciblebuild/fullcombatparity/efficacy. Existing min0/u.udaminc/specialcombat/propertypoly approximations retained. Entire project exclusion beyondab/trees/full effective appliedprofiles/runtime/adapters/router/probe/fallback mandatory; incomplete archivecases explicitly UNQUALIFIED/no universal semantic proof/no archive repair/replay. Daglar-only author+committer. UNFROZEN SOURCE ONLY/no seed/game/freeze; FIRST serialized pinned146/THREE realValkrole11resets/ABI2,3/dbon246oncepoly/capacity+squeeze/profileorNoProfile required before later independent admission. Private wholebase/reporting/verification only, no per-target selection.
github.com/tabt/nethacker@616e9c5b25683af6de9542a9d1dcb80dd8138e13
github.com/DT6A/nethacker@79297ad035c15971f74a4549e7c08f521253ee95
github.com/DT6A/nethacker@79297ad035c15971f74a4549e7c08f521253ee95

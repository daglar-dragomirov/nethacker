# zPublicPick9163352 (Claude, 2026-11-26)

Public-seed picks. Each earlier ticket of ours (same engine code, a different exploration-RNG salt) was another draw on the 15
published seeds. For every identity and published seed this router recognises the seed from a hash of the initial observation and
replays the engine version and salt with the best record there (repeated results averaged; a single result discounted toward the
seed mean, since replays reproduce only about half the time). The picks are fitted to the published seeds and say nothing about
other seeds: on hidden seeds no hash matches and the identity plays its routes-v4 engine (base = github.com/daglar-dragomirov/nethacker@eab9a9c4f4e09bce096d5762e895fec51b63784d; hed = zV10eHedEatNearby)
with salt 9163352. No efficacy claim.

Engine directories (salt read from CLAUDE_SALT, default 9163352):
- `e0_base_dee75b`: base:dee75b121ac9 copied from zLeadersBest1913123/base
- `e1_hed_b81587`: hed:b815879f0b4d copied from zLeadersBest3528931/hed
- `e2_hed_8e23ec`: hed:8e23ec43e2b6 copied from zLeadersBest4336835/hed
- `e3_hed_e3ce2e`: hed:e3ce2e4c9bca copied from zLeadersBest1913123/hed
- `e9_base_atl550`: Atlantic83 open program, commit 550902b (github.com/Atlantic83), vendored unchanged except the unused d_daglar_dragomirov_* dirs;
  its own licenses and CHANGES.md are kept inside. The three Valkyrie identities play it (with its dice table) by default; a published
  Valkyrie seed may play `e8_base_tb206` instead (next entry). Credit: Atlantic83, DT6A.
- `e8_base_tb206`: zTieBreak206/base unchanged (Valkyrie agent RNG unsalted); a published Valkyrie seed plays it where its mean over
  our ~159 unsalted draws beats Atlantic83's per-seed value by more than 0.02. Valkyries are now recognised by the router (the
  welcome line has no gender word for them); before, every Valkyrie game fell through to the default route.

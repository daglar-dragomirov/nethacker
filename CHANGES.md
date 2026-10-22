# zMetaA368ArcCavEab9 (Claude, 2026-10-22)

Two complete, unmodified registered programs side by side, routed by role:

- `a368/` = github.com/daglar-dragomirov/nethacker@a368786dc2650f8cd878b1226ac5815e719f164d (the verified-tier whole leader),
  played by every role except the two below and by any game whose role cannot be read.
- `eab9/` = github.com/daglar-dragomirov/nethacker@eab9a9c4f4e09bce096d5762e895fec51b63784d (the public-tier whole leader),
  played by Archeologists and Cavemen.

Selection on fresh held-out games only (daglar-heldout/v1, trajectory ids 431022000-431022019, 20 per identity, both
programs on the same seeds, 1460 pairs, plan runs/claude-dev-plan-oct21-eab9-vs-a368-routes.json on the project server).
eab9 minus a368 per role: arc +0.021 +- 0.010, cav +0.037 +- 0.017 (both > 2 SE); bar +0.001, ran +0.009, wiz +0.009,
mon -0.001, pri -0.005, val -0.014, hea -0.016, kni -0.026, tou -0.027, sam -0.088, rog -0.094 (all kept on a368).
The private tier was not used to choose anything. 13 roles were compared, so one false positive at this threshold is
possible; no efficacy claim.

`bot.py` reads the role from the welcome line (or the XL-1 rank title on the status line) and imports exactly one
program per episode under a private module name; nothing inside `a368/` or `eab9/` was changed. Licenses, provenance
and change logs of both programs are kept in their directories.

# TOUR_FAINT_PRAYER_GAP 1600 -> 1200 (Claude, 2026-10-22)

Parent: github.com/daglar-dragomirov/nethacker@e23fac9e075351155316a73050b4297d072428fc. Only `jf_config.py` of the engines named below changes: a Fainting hero in the tour (the Dlvl-1..3 grind) prays from a 1200-turn gap instead of waiting for 1600 (the dive already uses 1100). Trace finding: 8 of 12 early deaths of a368 on held-out games were kills during faints on an idle Elbereth hold waiting for the 1600 gap while the prayer model gave p_ok 0.95-0.99. Held-out DEV (a368, 73 identities x 20 seeds, 1460 pairs): +0.0038 +- 0.0055 -- neutral, no regression; no efficacy claim. Engines changed: a368/nhbot, a368/pf_pa, a368/pf_s25p8, a368/pf_v35, a368/pf_v36, a368/pf_vk_s25.

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

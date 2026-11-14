# nethack

A NetHack 3.6.6 bot for [NetHackers](https://nethackers.dunnolab.ai/).

The repository root is the solution: `bot.py` exposes `make_agent()` (the hub's verifier scores the repo root).

- `nhbot/` — the main engine, an AutoAscend descendant forked from daglar-dragomirov/nethacker's `pf_s25p`
  (vkurenkov's "jawfish" s25 line); MIT, see `LICENSE`.
- `pf_hg/`, `pf_hh/`, `pf_pa/`, `pf_v35/`, `pf_v25/` — specialist engines from the same lineage, routed per identity
  in `bot.py` (Healers, Samurai), as in daglar-dragomirov/nethacker@e29eb82 (`pf_pa`, `pf_v25`: no longer routed).
- `roles.py` — per-identity overrides of engine settings.
- `tools/` (evaluation and hub-registration helpers of the parent repository, never imported by the bot) was
  removed from this copy; see the parent commits in `nethackers.solution.json` for them.

Changes over the parent engines are listed in `CHANGES.md`.

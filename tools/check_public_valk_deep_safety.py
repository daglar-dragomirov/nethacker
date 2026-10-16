#!/usr/bin/env python3
"""Source contract for the PublicValkDeepSafety derivative; this runs no games."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True


BASE_SHA = "cc23cb3c053e5424e674067b868f86b90ab8a2a8"
BASE_TREE = "f92e10b7521e9b66a2c2372880d4728173d4583d"
SOURCE_SHA = "69b37e2a25dc114121b7771bf381650833134db3"
SOURCE_TREE = "e4217080ebd288c3e15ab46e9293b21846a339e2"
SOURCE_ZIP_SHA256 = "a2498640b1a6866a1d3740e7af42f3ddcdb4df71432d9c208ca2aefe6d964c22"
SOURCE_ZIP_PREFIX = f"nethacker-{SOURCE_SHA}/"
VALK_ROUTES = {
    "val-dwa-law-fem": "adapter_pf_vk_s23_valk_deep_safety",
    "val-hum-law-fem": "adapter_nhbot_valk_deep_safety",
    "val-hum-neu-fem": "adapter_nhbot_v3_valk_deep_safety",
}
PACKAGE_SOURCES = {
    "nhbot_valk_deep_safety": "nhbot",
    "nhbot_v3_valk_deep_safety": "nhbot_v3",
    "pf_vk_s23_valk_deep_safety": "pf_vk_s23",
}
ADAPTER_SOURCES = {
    "adapter_nhbot_valk_deep_safety.py": ("adapter.py", "nhbot_valk_deep_safety", "nhbot"),
    "adapter_nhbot_v3_valk_deep_safety.py":
        ("adapter_nhbot_v3.py", "nhbot_v3_valk_deep_safety", "nhbot_v3"),
    "adapter_pf_vk_s23_valk_deep_safety.py":
        ("adapter_pf_vk_s23.py", "pf_vk_s23_valk_deep_safety", "pf_vk_s23"),
}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def load_bot(root: Path, module_name: str):
    old_roles = sys.modules.pop("roles", None)
    sys.path.insert(0, str(root))
    try:
        spec = importlib.util.spec_from_file_location(module_name, root / "bot.py")
        check(spec is not None and spec.loader is not None, f"cannot load {root / 'bot.py'}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)
        sys.modules.pop("roles", None)
        if old_roles is not None:
            sys.modules["roles"] = old_roles


def normalise_source(data: bytes, derived: str, source: str) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(derived.encode(), source.encode())


def scrub_poison_policy(data: bytes, relative: str) -> bytes:
    if relative == "global_logic.py":
        pattern = re.compile(
            rb"(?m)^\s{16}# (?:POISON_RES_EAT|PUBLIC_VALK_DEEP_SAFETY):.*?"
            rb"(?=^\s{16}self\.agent\.eat_from_inventory\(\)\.every\(5\),)",
            re.DOTALL,
        )
    elif relative == "jf_config.py":
        pattern = re.compile(
            rb"(?m)^(?:# hypothesis: a few corpses|# PUBLIC_VALK_DEEP_SAFETY:).*?"
            rb"^POISON_RES_EAT = True\r?\n(?:POISON_RES_DIST = 3\r?\n)?",
            re.DOTALL,
        )
    else:
        return data
    scrubbed, count = pattern.subn(b"<PUBLIC_VALK_POISON_POLICY>\n", data)
    check(count == 1, f"expected one poison policy block in {relative}, found {count}")
    return scrubbed


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    ):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def main() -> int:
    candidate = Path(__file__).resolve().parents[1]
    workspace = candidate.parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=workspace / "runs/zRayProbability-publication/repo")
    parser.add_argument("--source-zip", type=Path,
                        default=workspace / "runs/codex-oct16-1422-dt6a-69b37e2-source.zip")
    parser.add_argument("--rankings", type=Path, default=workspace / "runs/codex_rankings_latest.json")
    args = parser.parse_args()
    base = args.base.resolve()
    source_zip = args.source_zip.resolve()

    check(git("-C", str(base), "rev-parse", "HEAD").decode().strip() == BASE_SHA, "wrong base commit")
    check(git("-C", str(base), "rev-parse", "HEAD^{tree}").decode().strip() == BASE_TREE, "wrong base tree")
    check(hashlib.sha256(source_zip.read_bytes()).hexdigest() == SOURCE_ZIP_SHA256,
          "registered source archive bytes changed")

    ranking = json.loads(args.rankings.read_text(encoding="utf-8"))
    identities = sorted(x["identity"] for x in ranking["tiers"]["self-reported"]["identity_leaders"])
    check(len(identities) == 73 and len(set(identities)) == 73, "Public identity inventory is not 73 unique routes")
    base_bot = load_bot(base, "public_valk_base_bot")
    candidate_bot = load_bot(candidate, "public_valk_candidate_bot")
    route_fixtures = 0
    for ident in identities:
        for pre_ident in (ident, ident.split("-", 1)[0]):
            before = base_bot.route(ident, pre_ident)
            after = candidate_bot.route(ident, pre_ident)
            if ident in VALK_ROUTES:
                check(after[0] == VALK_ROUTES[ident], f"wrong derived route for {ident}/{pre_ident}: {after}")
                check(after[1] == before[1], f"roles-config contract changed for {ident}/{pre_ident}: {before} -> {after}")
            else:
                check(after == before, f"non-Valk route changed for {ident}/{pre_ident}: {before} -> {after}")
            route_fixtures += 1
    check(route_fixtures == 146, "route fixture count changed")

    allowed_base_changes = {"bot.py", "roles.py", "nethackers.solution.json", "CHANGES.md"}
    base_files = sorted(p.relative_to(base).as_posix() for p in base.rglob("*")
                        if p.is_file() and ".git" not in p.relative_to(base).parts
                        and "__pycache__" not in p.relative_to(base).parts)
    for relative in base_files:
        check((candidate / relative).is_file(), f"base file missing: {relative}")
        if relative not in allowed_base_changes:
            check((candidate / relative).read_bytes() == (base / relative).read_bytes(),
                  f"unrelated base file changed: {relative}")

    with zipfile.ZipFile(source_zip) as source_archive:
        source_names = set(source_archive.namelist())
        for derived, source in PACKAGE_SOURCES.items():
            archive_prefix = f"{SOURCE_ZIP_PREFIX}{source}/"
            expected_rel = sorted(path[len(archive_prefix):] for path in source_names
                                  if path.startswith(archive_prefix) and not path.endswith("/"))
            actual_rel = sorted(p.relative_to(candidate / derived).as_posix()
                                for p in (candidate / derived).rglob("*") if p.is_file())
            check(actual_rel == expected_rel, f"file inventory differs for {derived}")
            for relative in expected_rel:
                actual = normalise_source((candidate / derived / relative).read_bytes(), derived, source)
                expected = normalise_source(source_archive.read(archive_prefix + relative), source, source)
                if relative in {"global_logic.py", "jf_config.py"}:
                    actual = scrub_poison_policy(actual, relative)
                    expected = scrub_poison_policy(expected, relative)
                check(actual == expected, f"registered source drift in {derived}/{relative}")

    for derived_adapter, (base_adapter, derived, source) in ADAPTER_SOURCES.items():
        actual = normalise_source((candidate / derived_adapter).read_bytes(), derived, source)
        expected = normalise_source((base / base_adapter).read_bytes(), source, source)
        check(actual == expected, f"adapter drift in {derived_adapter}")

    safety_needles = (
        "only_below_me=True",
        "hunger_state >= Hunger.NOT_HUNGRY",
        "hitpoints >= 0.5 * self.agent.blstats.max_hitpoints",
        "not self.dive._near_hostiles(radius=99)",
        "not self.agent._hurt_recently(6)",
    )
    for derived in PACKAGE_SOURCES:
        global_logic = (candidate / derived / "global_logic.py").read_text(encoding="utf-8")
        config = (candidate / derived / "jf_config.py").read_text(encoding="utf-8")
        for needle in safety_needles:
            check(needle in global_logic, f"missing safety guard {needle!r} in {derived}")
        check("POISON_RES_DIST" not in global_logic + config, f"distance poison route remains in {derived}")

    bot_source = (candidate / "bot.py").read_text(encoding="utf-8")
    roles_source = (candidate / "roles.py").read_text(encoding="utf-8")
    check("roles.apply(ident, package=package)" in bot_source, "dedicated package does not receive role overrides")
    check('def apply(ident: str | None, package: str = "nhbot")' in roles_source,
          "roles.apply package contract missing")

    manifest = json.loads((candidate / "nethackers.solution.json").read_text(encoding="utf-8"))
    parents = set(manifest["parents"])
    check(f"github.com/daglar-dragomirov/nethacker@{BASE_SHA}" in parents, "base provenance missing")
    check(f"github.com/DT6A/nethacker@{SOURCE_SHA}" in parents, "registered source provenance missing")
    check("github.com/DT6A/nethacker@aef056b100c5184353f6274216f4721c6cb4b0c5" in parents,
          "registered parent provenance missing")
    check((candidate / "LICENSE").read_bytes() == (base / "LICENSE").read_bytes(), "MIT license changed")
    check((candidate / "LICENSE_DT6A_ad7a").read_bytes() == (base / "LICENSE_DT6A_ad7a").read_bytes(),
          "DT6A license changed")

    print(json.dumps({
        "status": "pass",
        "base_sha": BASE_SHA,
        "base_tree": BASE_TREE,
        "source_sha": SOURCE_SHA,
        "source_tree": SOURCE_TREE,
        "identities": len(identities),
        "route_fixtures": route_fixtures,
        "changed_effective_routes": sorted(VALK_ROUTES),
        "unchanged_effective_routes": len(identities) - len(VALK_ROUTES),
        "candidate_digest": tree_digest(candidate),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

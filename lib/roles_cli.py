"""Unified-CLI integration for `roles` (plural, query) and `role` (singular, mutate)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib import agent as _agent

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _find_dispatcher():
    """Locate the brm dispatcher module regardless of how it was loaded.

    When invoked via `python scripts/brm`, the dispatcher runs as `__main__`.
    When imported as a library (e.g. in tests), it may be under `scripts.brm`.
    Fall back to loading the file from disk so `lib.roles_cli` can also be
    imported standalone.
    """
    for name in ("__main__", "scripts.brm"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "register_noun"):
            return mod
    # Fallback: load the dispatcher from disk.  `scripts/brm` has no `.py`
    # extension, so `spec_from_file_location` would return None without an
    # explicit loader — pass SourceFileLoader to avoid the latent crash.
    from importlib import machinery as _mach, util as _util
    path = Path(__file__).resolve().parent.parent / "scripts" / "brm"
    loader = _mach.SourceFileLoader("scripts.brm", str(path))
    spec = _util.spec_from_file_location("scripts.brm", str(path), loader=loader)
    mod = _util.module_from_spec(spec)
    sys.modules["scripts.brm"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# roles (plural) — query noun
# ---------------------------------------------------------------------------

def _add_roles_list(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("list", help="List roles")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--include-custom",
        action="store_true",
        help="Include custom agents from .brm/agents/",
    )


def dispatch_roles_list(args: argparse.Namespace) -> int:
    found = _agent.discover_agents(
        plugin_root=PLUGIN_ROOT,
        project_root=Path.cwd() if args.include_custom else None,
        global_root=(Path.home() / ".brm" / "agents") if args.include_custom else Path("/dev/null"),
    )
    roles = [a for a in found.values() if a.kind in ("strategic", "tactical")]
    helpers = [a for a in found.values() if a.kind == "helper"]
    roles.sort(key=lambda a: a.name)
    if args.json:
        out = [
            {
                "name": a.name,
                "kind": a.kind,
                "title": a.title,
                "anchor_skill": a.anchor_skill,
                "helpers": a.helpers,
            }
            for a in roles
        ]
        print(json.dumps(out, indent=2))
        return 0
    print(f"Roles ({len(roles)}):")
    for a in roles:
        print(f"  {a.kind:10s}  {a.name:18s}  {a.title}")
    if args.include_custom and helpers:
        print(f"\nHelpers ({len(helpers)}):")
        for a in sorted(helpers, key=lambda a: a.name):
            print(f"  helper      {a.name:18s}  {a.title}")
    return 0


# ---------------------------------------------------------------------------
# role (singular) — mutation noun
# ---------------------------------------------------------------------------

def _add_role_new(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("new", help="Scaffold a new custom role")
    p.add_argument("name")
    p.add_argument("--kind", choices=("strategic", "tactical"), required=True)
    p.add_argument("--from-template", default=None)


def _add_role_delete(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("delete", help="Delete a custom role (built-ins refused)")
    p.add_argument("name")


_TEMPLATE_PATHS = {
    "strategic": PLUGIN_ROOT / "agents" / "templates" / "strategic.md",
    "tactical": PLUGIN_ROOT / "agents" / "templates" / "tactical.md",
}


def dispatch_role_new(args: argparse.Namespace) -> int:
    name = args.name
    if not name.replace("-", "").isalnum() or not name[0].isalpha():
        print(
            f"role name must be alphanumeric/hyphenated starting with a letter: '{name}'",
            file=sys.stderr,
        )
        return 1
    agent_dir = Path.cwd() / ".brm" / "agents"
    cmd_dir = Path.cwd() / ".claude" / "commands"
    agent_dir.mkdir(parents=True, exist_ok=True)
    cmd_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agent_dir / f"{name}.md"
    cmd_file = cmd_dir / f"{name}.md"
    if agent_file.exists() or cmd_file.exists():
        print(f"role '{name}' already exists", file=sys.stderr)
        return 1

    template = (args.from_template and Path(args.from_template)) or _TEMPLATE_PATHS[args.kind]
    body = template.read_text().replace("{Name}", name.replace("-", " ").title()).replace("{name}", name)
    agent_file.write_text(body)
    wrapper = f"""---
description: Custom BRM role: {name}
brm-role: true
brm-agent: {name}
---

This is a BRM role activation. Read your agent definition at
`.brm/agents/{name}.md` (or the highest-priority override per BRM's discovery order)
and operate as that role.

Acknowledge `<brm-epic>` and `<brm-story>` blocks if present. Apply your anchor
skill per `<skills>`. Follow the handoff protocol when ready.
"""
    cmd_file.write_text(wrapper)
    print(f"created role '{name}': {agent_file} + {cmd_file}")
    return 0


def dispatch_role_delete(args: argparse.Namespace) -> int:
    name = args.name
    plugin_agent = PLUGIN_ROOT / "agents" / f"{name}.md"
    if plugin_agent.is_file():
        print(f"refusing to delete built-in role '{name}'", file=sys.stderr)
        return 1
    agent_file = Path.cwd() / ".brm" / "agents" / f"{name}.md"
    cmd_file = Path.cwd() / ".claude" / "commands" / f"{name}.md"
    found = False
    if agent_file.is_file():
        agent_file.unlink()
        found = True
    if cmd_file.is_file():
        cmd_file.unlink()
        found = True
    if not found:
        print(f"role '{name}' not found in project", file=sys.stderr)
        return 1
    print(f"deleted role '{name}'")
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _register() -> None:
    """Append roles/role noun parser builders to the unified CLI's NOUNS dict."""
    dispatcher = _find_dispatcher()

    # ---- roles (plural, query) ----
    roles_handler = dispatcher.register_noun(
        "roles", "List BRM roles (read-only query)"
    )
    _roles_list_name = f"{_add_roles_list.__module__}.{_add_roles_list.__qualname__}"
    roles_handler.add_subparsers[:] = [
        a for a in roles_handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in (_roles_list_name,)
    ]
    roles_handler.add_subparsers.append(_add_roles_list)
    roles_handler.dispatch_list = dispatch_roles_list

    # ---- role (singular, mutation) ----
    role_handler = dispatcher.register_noun(
        "role", "Create or delete a custom role"
    )
    _role_new_name = f"{_add_role_new.__module__}.{_add_role_new.__qualname__}"
    _role_delete_name = f"{_add_role_delete.__module__}.{_add_role_delete.__qualname__}"
    role_handler.add_subparsers[:] = [
        a for a in role_handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in (_role_new_name, _role_delete_name)
    ]
    role_handler.add_subparsers.append(_add_role_new)
    role_handler.dispatch_new = dispatch_role_new
    role_handler.add_subparsers.append(_add_role_delete)
    role_handler.dispatch_delete = dispatch_role_delete


_register()

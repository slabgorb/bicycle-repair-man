"""Unified-CLI integration for `repos`. Delegates to lib/orchestrator.py
(which already factors out the work shared with the v0.2 standalone script)."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from lib import orchestrator as _orch


def _find_dispatcher():
    """Locate the brm dispatcher module regardless of how it was loaded.

    When invoked via `python scripts/brm`, the dispatcher runs as `__main__`.
    When imported as a library (e.g. in tests), it may be under `scripts.brm`.
    Fall back to loading the file from disk so `lib.repos_cli` can also be
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
# Helpers shared between verbs
# ---------------------------------------------------------------------------

def _resolve_orchestrator_root(cwd: Path) -> Path | None:
    override = os.environ.get("BRM_ORCHESTRATOR_ROOT")
    if override:
        candidate = Path(override)
        if (candidate / ".brm" / "repos.yaml").is_file():
            return candidate
        return None
    return _orch.find_orchestrator_root(cwd)


def _die(msg: str, code: int = 1) -> None:
    print(f"brm repos: {msg}", file=sys.stderr)
    sys.exit(code)


def _require_orch_root() -> tuple[Path, dict[str, _orch.RepoConfig], str]:
    """Resolve orchestrator root, load repos.yaml. Exits 1 if not found."""
    root = _resolve_orchestrator_root(Path.cwd())
    if root is None:
        _die("not in an orchestrator workspace (no .brm/repos.yaml found)")
    text = (root / ".brm" / "repos.yaml").read_text(encoding="utf-8", errors="replace")
    try:
        repos = _orch.parse_repos_yaml(text)
    except _orch.RepoConfigError as e:
        _die(f"could not parse {root / '.brm' / 'repos.yaml'}: {e}")
    return root, repos, text


def _git(repo_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Verb: status
# ---------------------------------------------------------------------------

def _add_status(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("status", help="Show git status for all repos")
    p.add_argument("--brief", action="store_true")
    p.add_argument("--json", action="store_true")


def dispatch_status(args: argparse.Namespace) -> int:
    root, repos, _ = _require_orch_root()
    rows: list[dict] = []
    any_dirty = False
    for r in repos.values():
        repo_path = root / r.path
        if not (repo_path / ".git").exists():
            rows.append({"name": r.name, "missing": True})
            continue
        branch = _git(repo_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        porcelain = _git(repo_path, "status", "--porcelain").stdout
        dirty = bool(porcelain.strip())
        upstream = _git(repo_path, "rev-parse", "--abbrev-ref", "@{u}").stdout.strip()
        unpushed = False
        if upstream:
            unpushed = bool(
                _git(repo_path, "log", "@{u}..HEAD", "--oneline").stdout.strip()
            )
        rows.append({
            "name": r.name, "branch": branch, "dirty": dirty,
            "unpushed": unpushed, "missing": False,
        })
        if dirty or unpushed:
            any_dirty = True

    if args.json:
        import json as _json
        print(_json.dumps(rows))
    elif args.brief:
        for row in rows:
            if row.get("missing"):
                print(f"{row['name']:20s} MISSING")
            else:
                flags = ("*" if row["dirty"] else " ") + ("↑" if row["unpushed"] else " ")
                print(f"{row['name']:20s} {row['branch']:24s} {flags}")
    else:
        for row in rows:
            if row.get("missing"):
                print(f"== {row['name']} (missing on disk) ==")
                continue
            print(f"== {row['name']} ({row['branch']}) ==")
            if row["dirty"]:
                print(f"  dirty: uncommitted changes")
            if row["unpushed"]:
                print(f"  unpushed: commits ahead of upstream")
            if not row["dirty"] and not row["unpushed"]:
                print("  clean")
    return 1 if any_dirty else 0


# ---------------------------------------------------------------------------
# Verb: list
# ---------------------------------------------------------------------------

def _add_list(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("list", help="List declared repos")
    p.add_argument("--json", action="store_true")


def dispatch_list(args: argparse.Namespace) -> int:
    _, repos, _ = _require_orch_root()
    if args.json:
        import json as _json
        print(_json.dumps(
            [{"name": r.name, "path": r.path, "type": r.type} for r in repos.values()]
        ))
    else:
        for name in repos:
            print(name)
    return 0


# ---------------------------------------------------------------------------
# Verb: owns
# ---------------------------------------------------------------------------

def _add_owns(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("owns", help="Identify which repo a path belongs to")
    p.add_argument("path")


def dispatch_owns(args: argparse.Namespace) -> int:
    root, repos, _ = _require_orch_root()
    target = Path(args.path).resolve()
    candidates: list[tuple[Path, str]] = []
    for name, r in repos.items():
        candidates.append(((root / r.path).resolve(), name))
    candidates.sort(key=lambda p: len(str(p[0])), reverse=True)
    for repo_root, name in candidates:
        if target == repo_root or repo_root in target.parents:
            print(name)
            return 0
    _die(f"no repo owns: {args.path}", code=2)
    return 2  # unreachable


# ---------------------------------------------------------------------------
# Verb: describe
# ---------------------------------------------------------------------------

def _add_describe(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("describe", help="Describe a single repo")
    p.add_argument("name")
    p.add_argument("--json", action="store_true")


def dispatch_describe(args: argparse.Namespace) -> int:
    _, repos, _ = _require_orch_root()
    if args.name not in repos:
        _die(f"unknown repo: {args.name}", code=2)
    r = repos[args.name]
    if args.json:
        import json as _json
        print(_json.dumps({
            "name": r.name, "path": r.path, "type": r.type,
            "description": r.description, "default_branch": r.default_branch,
            "test_command": r.test_command, "lint_command": r.lint_command,
            "build_command": r.build_command,
        }))
    else:
        for field in ("name", "path", "type", "description", "default_branch",
                      "test_command", "lint_command", "build_command"):
            print(f"{field}: {getattr(r, field)}")
    return 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _register() -> None:
    """Append repos-noun parser builders to the unified CLI's NOUNS dict."""
    dispatcher = _find_dispatcher()
    handler = dispatcher.register_noun("repos", "Multi-repo workspace operations")

    _status_name = f"{_add_status.__module__}.{_add_status.__qualname__}"
    _list_name = f"{_add_list.__module__}.{_add_list.__qualname__}"
    _owns_name = f"{_add_owns.__module__}.{_add_owns.__qualname__}"
    _describe_name = f"{_add_describe.__module__}.{_add_describe.__qualname__}"

    handler.add_subparsers[:] = [
        a for a in handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in (_status_name, _list_name, _owns_name, _describe_name)
    ]
    handler.add_subparsers.append(_add_status)
    handler.dispatch_status = dispatch_status
    handler.add_subparsers.append(_add_list)
    handler.dispatch_list = dispatch_list
    handler.add_subparsers.append(_add_owns)
    handler.dispatch_owns = dispatch_owns
    handler.add_subparsers.append(_add_describe)
    handler.dispatch_describe = dispatch_describe


_register()

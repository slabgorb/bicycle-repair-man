"""Unified-CLI integration for the `epic` noun."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from lib import epic as _epic

_SLUG_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]*")


def _find_dispatcher():
    """Locate the brm dispatcher module regardless of how it was loaded.

    When invoked via `python scripts/brm`, the dispatcher runs as `__main__`.
    When imported as a library (e.g. in tests), it may be under `scripts.brm`.
    Fall back to loading the file from disk so `lib.epic_cli` can also be
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


def _add_create(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("create", help="Create a new epic")
    p.add_argument("slug")
    p.add_argument("--workflow", required=True)
    p.add_argument("--repos", required=True, help="comma-separated short-names")
    p.add_argument("--title", default=None)
    p.add_argument(
        "--require-approval",
        action="store_true",
        help="Require spec-approval gate before activate",
    )


def _add_list(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("list", help="List epics")
    p.add_argument("--status", choices=("draft", "active", "done", "all"), default="all")
    p.add_argument("--json", action="store_true")


def _add_describe(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("describe", help="Show epic details")
    p.add_argument("slug")


def _add_status(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("status", help="Show epic + story rollup")
    p.add_argument("slug")


def dispatch_create(args: argparse.Namespace) -> int:
    slug = args.slug
    if not _SLUG_RE.fullmatch(slug):
        print(
            f"slug must match [a-zA-Z0-9][a-zA-Z0-9._-]* — got {slug!r}",
            file=sys.stderr,
        )
        return 2
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("--repos must list at least one short-name", file=sys.stderr)
        return 2

    # Anchor at cwd.  Phase F will add walk-up resolution to find .brm/.
    brm_root = Path.cwd() / ".brm"
    epic_dir = brm_root / "epics" / slug
    if epic_dir.exists():
        print(f"epic '{slug}' already exists at {epic_dir}", file=sys.stderr)
        return 1

    epic_dir.mkdir(parents=True, exist_ok=False)
    (epic_dir / "stories").mkdir()

    approval = _epic.SpecApproval(required=True) if args.require_approval else None
    e = _epic.Epic(
        slug=slug,
        title=args.title or slug,
        status="draft",
        workflow=args.workflow,
        repos=repos,
        created=date.today().isoformat(),
        spec_approval=approval,
        body=f"# {args.title or slug}\n\n_(spec body — fill in via brainstorming)_\n",
    )
    (epic_dir / "epic.md").write_text(_epic.serialize_epic(e))
    # plan.md is created empty so writing-plans output has a destination.
    (epic_dir / "plan.md").write_text(f"# Implementation plan — {args.title or slug}\n\n")
    print(f"created epic at {epic_dir}")
    return 0


def dispatch_list(args: argparse.Namespace) -> int:
    import json
    epics_root = Path.cwd() / ".brm" / "epics"
    if not epics_root.is_dir():
        if args.json:
            print("[]")
        else:
            print("(no epics)")
        return 0
    entries = []
    for epic_dir in sorted(epics_root.iterdir()):
        epic_file = epic_dir / "epic.md"
        if not epic_file.is_file():
            continue
        try:
            e = _epic.parse_epic_text(epic_file.read_text())
        except _epic.EpicSchemaError:
            continue
        if args.status != "all" and e.status != args.status:
            continue
        entries.append(e)
    if args.json:
        print(json.dumps([
            {"slug": e.slug, "title": e.title, "status": e.status,
             "workflow": e.workflow, "repos": e.repos}
            for e in entries
        ], indent=2))
    else:
        if not entries:
            print("(no epics)")
        for e in entries:
            print(f"  {e.status:8s}  {e.slug:30s}  {e.title}")
    return 0


def _epic_path(slug: str) -> Path:
    return Path.cwd() / ".brm" / "epics" / slug / "epic.md"


def _load_epic(slug: str) -> _epic.Epic:
    path = _epic_path(slug)
    if not path.is_file():
        raise FileNotFoundError(f"epic '{slug}' not found at {path}")
    return _epic.parse_epic_text(path.read_text())


def dispatch_describe(args: argparse.Namespace) -> int:
    try:
        e = _load_epic(args.slug)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"slug:     {e.slug}")
    print(f"title:    {e.title}")
    print(f"status:   {e.status}")
    print(f"workflow: {e.workflow}")
    print(f"repos:    {', '.join(e.repos)}")
    print(f"created:  {e.created}")
    if e.current_story:
        print(f"current:  {e.current_story}")
    if e.spec_approval:
        sa = e.spec_approval
        approved = sa.approved_at or "(pending)"
        print(f"approval: required={sa.required} approved_at={approved}")
    return 0


def _add_activate(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("activate", help="Transition epic from draft to active")
    p.add_argument("slug")


def dispatch_activate(args: argparse.Namespace) -> int:
    try:
        e = _load_epic(args.slug)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if e.status != "draft":
        print(f"epic must be in 'draft' to activate (currently {e.status})", file=sys.stderr)
        return 1
    if e.spec_approval and e.spec_approval.required and not e.spec_approval.approved_at:
        print(
            f"epic '{args.slug}' requires spec approval. Run the gate via "
            f"`brm epic gate {args.slug}` (added in Phase F) and record the result "
            f"via `brm epic record-gate {args.slug} --result-stdin`.",
            file=sys.stderr,
        )
        return 1
    e.status = "active"
    _epic_path(args.slug).write_text(_epic.serialize_epic(e))
    print(f"epic '{args.slug}' activated")
    return 0


def dispatch_status(args: argparse.Namespace) -> int:
    try:
        e = _load_epic(args.slug)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    stories_dir = Path.cwd() / ".brm" / "epics" / args.slug / "stories"
    story_files = sorted(stories_dir.glob("*.md")) if stories_dir.is_dir() else []
    print(f"epic {e.slug} ({e.status})")
    print(f"stories: {len(story_files)}")
    # Per-status rollup populated in Phase D once stories have status.
    return 0


def _register() -> None:
    """Append epic-noun parser builders to the unified CLI's NOUNS dict."""
    dispatcher = _find_dispatcher()
    handler = dispatcher.register_noun(
        "epic", "Manage epics (the folder/spec layer above stories)"
    )
    # Guard against double-registration on module reload — argparse would
    # otherwise raise `ValueError: conflicting subparser: create` or `list`.
    # We can't rely on object identity because a reload creates fresh function
    # objects, so dedupe by qualified name.
    _create_name = f"{_add_create.__module__}.{_add_create.__qualname__}"
    _list_name = f"{_add_list.__module__}.{_add_list.__qualname__}"
    _describe_name = f"{_add_describe.__module__}.{_add_describe.__qualname__}"
    _status_name = f"{_add_status.__module__}.{_add_status.__qualname__}"
    _activate_name = f"{_add_activate.__module__}.{_add_activate.__qualname__}"
    handler.add_subparsers[:] = [
        a for a in handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in (_create_name, _list_name, _describe_name, _status_name, _activate_name)
    ]
    handler.add_subparsers.append(_add_create)
    handler.add_subparsers.append(_add_list)
    handler.add_subparsers.append(_add_describe)
    handler.add_subparsers.append(_add_status)
    handler.add_subparsers.append(_add_activate)
    handler.dispatch_create = dispatch_create
    handler.dispatch_list = dispatch_list
    handler.dispatch_describe = dispatch_describe
    handler.dispatch_status = dispatch_status
    handler.dispatch_activate = dispatch_activate


_register()

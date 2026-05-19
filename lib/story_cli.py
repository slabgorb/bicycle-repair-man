"""Unified-CLI integration for the `story` noun."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lib import epic as _epic
from lib import plan as _plan
from lib import story as _story


def _find_dispatcher():
    """Locate the brm dispatcher module regardless of how it was loaded.

    When invoked via `python scripts/brm`, the dispatcher runs as `__main__`.
    When imported as a library (e.g. in tests), it may be under `scripts.brm`.
    Fall back to loading the file from disk so `lib.story_cli` can also be
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


def _add_split(verb_subs: argparse._SubParsersAction) -> None:
    p = verb_subs.add_parser("split", help="Extract stories from plan.md")
    p.add_argument("epic_slug")
    p.add_argument("--force", action="store_true",
                   help="Allow slug renames; overwrite existing stories on mismatch")


def _epic_dir(epic_slug: str) -> Path:
    return Path.cwd() / ".brm" / "epics" / epic_slug


def _known_workflows() -> set[str]:
    plugin_root = Path(__file__).resolve().parent.parent
    builtin = {p.stem for p in (plugin_root / "workflows").glob("*.yaml")}
    orch_override = Path.cwd() / ".brm" / "workflows"
    if orch_override.is_dir():
        builtin |= {p.stem for p in orch_override.glob("*.yaml")}
    return builtin


def _known_repos() -> set[str]:
    # Reads .brm/repos.yaml if present (v0.2 orchestrator manifest).
    repos_yaml = Path.cwd() / ".brm" / "repos.yaml"
    if not repos_yaml.is_file():
        return set()
    import yaml
    try:
        doc = yaml.safe_load(repos_yaml.read_text()) or {}
    except yaml.YAMLError:
        return set()
    return set((doc.get("repos") or {}).keys())


def dispatch_split(args: argparse.Namespace) -> int:
    epic_dir = _epic_dir(args.epic_slug)
    epic_file = epic_dir / "epic.md"
    plan_file = epic_dir / "plan.md"
    if not epic_file.is_file():
        print(f"epic '{args.epic_slug}' not found at {epic_file}", file=sys.stderr)
        return 1
    if not plan_file.is_file():
        print(f"plan.md missing under {epic_dir}", file=sys.stderr)
        return 1

    try:
        e = _epic.parse_epic_text(epic_file.read_text())
    except _epic.EpicSchemaError as exc:
        print(f"epic.md malformed: {exc}", file=sys.stderr)
        return 1

    try:
        plan = _plan.parse_plan_text(plan_file.read_text())
    except _plan.PlanParseError as exc:
        print(f"plan.md parse error: {exc}", file=sys.stderr)
        return 1

    if not plan.stories:
        print(
            f"plan.md contains no `## Story: <title>` markers. Example:\n\n"
            f"  ## Story: My first story\n\n"
            f"  ```yaml\n  slug: 01-my-first\n  acceptance:\n    - \"first AC\"\n  ```\n\n"
            f"  Body of the story.\n",
            file=sys.stderr,
        )
        return 1

    known_repos = _known_repos() or set(e.repos)
    known_workflows = _known_workflows()
    errors = _plan.validate_plan(plan, known_repos=known_repos, known_workflows=known_workflows)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    stories_dir = epic_dir / "stories"
    stories_dir.mkdir(exist_ok=True)
    created, updated = [], []
    for ps in plan.stories:
        target = stories_dir / f"{ps.slug}.md"
        if target.is_file():
            # Re-split merge handled in Task D3.
            updated.append(target)
            continue
        story = _story.Story(
            slug=ps.slug,
            title=ps.title,
            epic=e.slug,
            workflow=ps.workflow or e.workflow,
            repos=ps.repos or list(e.repos),
            status="draft",
            phase=None,
            phase_history=[],
            acceptance=[{"done": False, "text": ac} for ac in ps.acceptance],
            body=f"# {ps.title}\n\n{ps.body}\n",
        )
        target.write_text(_story.serialize_story(story))
        created.append(target)

    print(f"created {len(created)} stories, updated {len(updated)}")
    return 0


def _register() -> None:
    """Append story-noun parser builders to the unified CLI's NOUNS dict."""
    dispatcher = _find_dispatcher()
    handler = dispatcher.register_noun(
        "story", "Manage stories (the implementation-unit layer)"
    )
    # Guard against double-registration on module reload — argparse would
    # otherwise raise `ValueError: conflicting subparser: split`.
    # Dedupe by qualified name (same pattern as lib/epic_cli.py).
    _split_name = f"{_add_split.__module__}.{_add_split.__qualname__}"
    handler.add_subparsers[:] = [
        a for a in handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in (_split_name,)
    ]
    handler.add_subparsers.append(_add_split)
    handler.dispatch_split = dispatch_split


_register()

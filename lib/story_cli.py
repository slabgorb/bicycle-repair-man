"""Unified-CLI integration for the `story` noun."""
from __future__ import annotations

import argparse
import re as _re
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
            existing = _story.parse_story_text(target.read_text())
            existing.title = ps.title  # title can change with header rename
            # Workflow override: plan wins if present, else keep what's there
            if ps.workflow is not None:
                existing.workflow = ps.workflow
            if ps.repos is not None:
                existing.repos = list(ps.repos)
            # Acceptance merge: preserve `done` flags by text match; new ACs unchecked
            existing_by_text = {ac["text"]: ac for ac in existing.acceptance}
            merged = []
            for ac_text in ps.acceptance:
                if ac_text in existing_by_text:
                    merged.append(existing_by_text[ac_text])
                else:
                    merged.append({"done": False, "text": ac_text})
            existing.acceptance = merged
            # Body replaced verbatim
            existing.body = f"# {ps.title}\n\n{ps.body}\n"
            target.write_text(_story.serialize_story(existing))
            updated.append(target)
            continue
        # New story (existing creation logic)
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

    plan_slugs = {ps.slug for ps in plan.stories}
    orphans = []
    for sf in stories_dir.glob("*.md"):
        slug = sf.stem
        if slug not in plan_slugs:
            orphans.append(sf.name)
    if orphans:
        print(f"warning: {len(orphans)} story file(s) no longer in plan: "
              f"{', '.join(orphans)} (not deleted)", file=sys.stderr)

    print(f"created {len(created)} stories, updated {len(updated)}")
    return 0


def _stories_dir(epic_slug: str) -> Path:
    return _epic_dir(epic_slug) / "stories"


def _resolve_story_slug(epic_slug: str, explicit: str | None) -> str:
    """If --story given, use it; otherwise read epic.current_story."""
    if explicit:
        return explicit
    epic_file = _epic_dir(epic_slug) / "epic.md"
    if not epic_file.is_file():
        raise FileNotFoundError(f"epic '{epic_slug}' not found")
    e = _epic.parse_epic_text(epic_file.read_text())
    if not e.current_story:
        raise ValueError(
            f"epic '{epic_slug}' has no current_story pointer; pass --story <slug>"
        )
    return e.current_story


def _load_story(epic_slug: str, story_slug: str) -> _story.Story:
    path = _stories_dir(epic_slug) / f"{story_slug}.md"
    if not path.is_file():
        raise FileNotFoundError(f"story '{story_slug}' not found in epic '{epic_slug}'")
    return _story.parse_story_text(path.read_text())


def _save_story(epic_slug: str, s: _story.Story) -> None:
    path = _stories_dir(epic_slug) / f"{s.slug}.md"
    path.write_text(_story.serialize_story(s))


def dispatch_list(args: argparse.Namespace) -> int:
    sdir = _stories_dir(args.epic_slug)
    if not sdir.is_dir():
        print(f"epic '{args.epic_slug}' has no stories"); return 0
    files = sorted(sdir.glob("*.md"))
    if not files:
        print("(no stories)"); return 0
    for f in files:
        try:
            s = _story.parse_story_text(f.read_text())
        except _story.StorySchemaError:
            continue
        phase = s.phase or "-"
        print(f"  {s.status:11s}  {phase:10s}  {s.slug:30s}  {s.title}")
    return 0


def dispatch_describe(args: argparse.Namespace) -> int:
    try:
        slug = _resolve_story_slug(args.epic_slug, args.story_slug)
        s = _load_story(args.epic_slug, slug)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr); return 1
    print(f"slug:     {s.slug}")
    print(f"title:    {s.title}")
    print(f"epic:     {s.epic}")
    print(f"workflow: {s.workflow}")
    print(f"repos:    {', '.join(s.repos)}")
    print(f"status:   {s.status}")
    print(f"phase:    {s.phase or '-'}")
    if s.acceptance:
        print("acceptance:")
        for ac in s.acceptance:
            mark = "x" if ac.get("done") else " "
            print(f"  [{mark}] {ac['text']}")
    return 0


def dispatch_status(args: argparse.Namespace) -> int:
    return dispatch_describe(args)  # same content for now; richer rollup in Plan 2


def dispatch_switch(args: argparse.Namespace) -> int:
    epic_file = _epic_dir(args.epic_slug) / "epic.md"
    if not epic_file.is_file():
        print(f"epic '{args.epic_slug}' not found", file=sys.stderr); return 1
    target = _stories_dir(args.epic_slug) / f"{args.story_slug}.md"
    if not target.is_file():
        print(f"story '{args.story_slug}' not found", file=sys.stderr); return 1
    e = _epic.parse_epic_text(epic_file.read_text())
    e.current_story = args.story_slug
    epic_file.write_text(_epic.serialize_epic(e))
    print(f"current_story set to {args.story_slug}")
    return 0


_HANDOFF_OPEN_RE = _re.compile(
    r'<handoff\s+from="([^"]+)"\s+to="([^"]+)"\s+repo="([^"]+)"\s+'
    r'agent="([^"]+)"\s+at="([^"]+)"\s*>'
)


def dispatch_handoff(args: argparse.Namespace) -> int:
    try:
        slug = _resolve_story_slug(args.epic_slug, args.story_slug)
        s = _load_story(args.epic_slug, slug)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr); return 1

    if args.stdin:
        block = sys.stdin.read()
    else:
        block = Path(args.file).read_text()

    m = _HANDOFF_OPEN_RE.search(block)
    if not m:
        print("input does not contain a valid <handoff ...> block", file=sys.stderr)
        return 1
    body_match = _re.search(r'<handoff[^>]*>\s*(.*?)\s*</handoff>', block, _re.DOTALL)
    body_text = body_match.group(1) if body_match else ""

    s.last_handoff = {
        "from": args.from_phase,
        "to": args.to_phase,
        "at": m.group(5),
        "body": body_text,
    }
    # Append to body log
    if "## Handoff log" not in s.body:
        s.body += "\n\n## Handoff log\n"
    s.body += f"\n### {args.from_phase} → {args.to_phase} ({m.group(5)})\n\n{body_text}\n"
    _save_story(args.epic_slug, s)
    print(f"handoff recorded: {args.from_phase} → {args.to_phase}")
    return 0


def _register() -> None:
    """Append story-noun parser builders to the unified CLI's NOUNS dict."""
    dispatcher = _find_dispatcher()
    handler = dispatcher.register_noun(
        "story", "Manage stories (the implementation-unit layer)"
    )
    # Guard against double-registration on module reload — argparse would
    # otherwise raise `ValueError: conflicting subparser: split/list/...`.
    # Dedupe by qualified name (same pattern as lib/epic_cli.py).
    _split_name = f"{_add_split.__module__}.{_add_split.__qualname__}"

    def _add_list(verb_subs):
        p = verb_subs.add_parser("list", help="List stories in an epic")
        p.add_argument("epic_slug")

    def _add_describe(verb_subs):
        p = verb_subs.add_parser("describe", help="Show story details")
        p.add_argument("epic_slug")
        p.add_argument("--story", dest="story_slug", default=None)

    def _add_status(verb_subs):
        p = verb_subs.add_parser("status", help="Show story state")
        p.add_argument("epic_slug")
        p.add_argument("--story", dest="story_slug", default=None)

    def _add_switch(verb_subs):
        p = verb_subs.add_parser("switch", help="Set epic's current_story pointer")
        p.add_argument("epic_slug")
        p.add_argument("story_slug")

    def _add_handoff(verb_subs):
        p = verb_subs.add_parser("handoff", help="Record a phase handoff")
        p.add_argument("epic_slug")
        p.add_argument("--story", dest="story_slug", default=None)
        p.add_argument("--from", dest="from_phase", required=True)
        p.add_argument("--to", dest="to_phase", required=True)
        src = p.add_mutually_exclusive_group(required=True)
        src.add_argument("--file", default=None)
        src.add_argument("--stdin", action="store_true")

    _list_name = f"{_add_list.__module__}.{_add_list.__qualname__}"
    _describe_name = f"{_add_describe.__module__}.{_add_describe.__qualname__}"
    _status_name = f"{_add_status.__module__}.{_add_status.__qualname__}"
    _switch_name = f"{_add_switch.__module__}.{_add_switch.__qualname__}"
    _handoff_name = f"{_add_handoff.__module__}.{_add_handoff.__qualname__}"
    _dedup_names = (
        _split_name, _list_name, _describe_name, _status_name, _switch_name, _handoff_name
    )
    handler.add_subparsers[:] = [
        a for a in handler.add_subparsers
        if f"{getattr(a, '__module__', '')}.{getattr(a, '__qualname__', '')}"
        not in _dedup_names
    ]
    handler.add_subparsers.append(_add_split)
    handler.dispatch_split = dispatch_split
    handler.add_subparsers.append(_add_list)
    handler.dispatch_list = dispatch_list
    handler.add_subparsers.append(_add_describe)
    handler.dispatch_describe = dispatch_describe
    handler.add_subparsers.append(_add_status)
    handler.dispatch_status = dispatch_status
    handler.add_subparsers.append(_add_switch)
    handler.dispatch_switch = dispatch_switch
    handler.add_subparsers.append(_add_handoff)
    handler.dispatch_handoff = dispatch_handoff


_register()

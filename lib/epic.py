"""Epic data model, parse, serialize, and lifecycle transitions for BRM v0.4."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import yaml

_VALID_STATUS = ("draft", "active", "done")
_REQUIRED_KEYS = ("schema", "slug", "title", "status", "workflow", "repos", "created")
_SCHEMA_PREFIX = "brm-epic/"


class EpicSchemaError(Exception):
    """Raised when an epic file is malformed."""


class EpicTransitionError(Exception):
    """Raised when a lifecycle transition is illegal."""


@dataclass
class SpecApproval:
    required: bool = False
    approved_at: str | None = None
    approver: str | None = None


@dataclass
class Epic:
    slug: str
    title: str
    status: str            # "draft" | "active" | "done"
    workflow: str
    repos: list[str]
    created: str           # ISO date
    current_story: str | None = None
    spec_approval: SpecApproval | None = None
    schema: str = "brm-epic/0.4"
    body: str = ""

    def is_terminal(self) -> bool:
        return self.status == "done"


def parse_epic_text(text: str) -> Epic:
    fm, body = _split_frontmatter(text)
    try:
        doc = yaml.safe_load(fm)
    except yaml.YAMLError as e:
        raise EpicSchemaError(f"YAML parse error: {e}") from e
    if not isinstance(doc, dict):
        raise EpicSchemaError("epic frontmatter must be a mapping")

    for key in _REQUIRED_KEYS:
        if key not in doc:
            raise EpicSchemaError(f"missing required field: {key}")

    schema = str(doc["schema"])
    if not schema.startswith(_SCHEMA_PREFIX):
        raise EpicSchemaError(f"unsupported schema: {schema}")

    status = doc["status"]
    if status not in _VALID_STATUS:
        raise EpicSchemaError(
            f"status must be one of {_VALID_STATUS}, got {status!r}"
        )

    repos = doc["repos"]
    if not isinstance(repos, list) or not all(isinstance(r, str) for r in repos):
        raise EpicSchemaError("repos must be a list of short-names")

    approval = None
    if "spec_approval" in doc and doc["spec_approval"] is not None:
        sa = doc["spec_approval"]
        if not isinstance(sa, dict):
            raise EpicSchemaError("spec_approval must be a mapping")
        raw_at = sa.get("approved_at")
        approval = SpecApproval(
            required=bool(sa.get("required", False)),
            approved_at=_normalize_datetime_str(raw_at),
            approver=sa.get("approver"),
        )

    return Epic(
        slug=str(doc["slug"]),
        title=str(doc["title"]),
        status=status,
        workflow=str(doc["workflow"]),
        repos=list(repos),
        created=str(doc["created"]),
        current_story=doc.get("current_story"),
        spec_approval=approval,
        schema=schema,
        body=body,
    )


def serialize_epic(e: Epic) -> str:
    fm: dict[str, Any] = {
        "schema": e.schema,
        "slug": e.slug,
        "title": e.title,
        "status": e.status,
        "workflow": e.workflow,
        "repos": list(e.repos),
        "created": e.created,
    }
    if e.current_story is not None:
        fm["current_story"] = e.current_story
    if e.spec_approval is not None:
        sa = {"required": e.spec_approval.required}
        if e.spec_approval.approved_at:
            sa["approved_at"] = e.spec_approval.approved_at
        if e.spec_approval.approver:
            sa["approver"] = e.spec_approval.approver
        fm["spec_approval"] = sa
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + e.body


def _normalize_datetime_str(value: Any) -> str | None:
    """Return ISO-8601 string with Z suffix from a pyyaml-parsed datetime or str."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)\Z", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = _FM_RE.match(text)
    if not m:
        raise EpicSchemaError("epic file must begin with YAML frontmatter")
    return m.group(1), m.group(2).lstrip("\n")


def find_active_epic(start: "Path", *, max_levels: int = 20) -> "tuple[Epic, Path] | None":
    """Walk up from `start` looking for an active or draft epic.

    Searches `<ancestor>/.brm/epics/*/epic.md`. Returns the (epic, dir) for the
    most preferred match:
      1. Any epic with status=active and a current_story pointer
      2. Any epic with status=active
      3. Any epic with status=draft
      4. None

    First-match-wins on ties (deterministic via sorted slug).
    """
    from pathlib import Path
    cur = Path(start).resolve()
    for _ in range(max_levels):
        epics_dir = cur / ".brm" / "epics"
        if epics_dir.is_dir():
            candidates: list[tuple[int, str, Epic, "Path"]] = []
            for d in sorted(epics_dir.iterdir()):
                if d.name.startswith("."):
                    continue
                ef = d / "epic.md"
                if not ef.is_file():
                    continue
                try:
                    e = parse_epic_text(ef.read_text())
                except EpicSchemaError:
                    continue
                priority = {"active": 0, "draft": 2, "done": 3}.get(e.status, 4)
                if e.status == "active" and e.current_story:
                    priority = -1  # most preferred
                candidates.append((priority, e.slug, e, d))
            if candidates:
                candidates.sort()
                _, _, e, d = candidates[0]
                return (e, d)
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def render_epic_block(e: "Epic", *, stories_root: "Path") -> str:
    """Render the <brm-epic> XML block for hook injection."""
    lines = ["<brm-epic>"]
    lines.append(f"  <slug>{_xml_escape(e.slug)}</slug>")
    lines.append(f"  <title>{_xml_escape(e.title)}</title>")
    lines.append(f"  <status>{e.status}</status>")
    lines.append(f"  <workflow>{_xml_escape(e.workflow)}</workflow>")
    lines.append(f"  <repos>{','.join(_xml_escape(r) for r in e.repos)}</repos>")
    if e.current_story:
        lines.append(f"  <current-story>{_xml_escape(e.current_story)}</current-story>")
    lines.append("  <stories>")
    if stories_root.is_dir():
        import yaml
        for sf in sorted(stories_root.glob("*.md")):
            try:
                doc, _ = sf.read_text().split("---\n", 2)[1:]
                fm = yaml.safe_load(doc) or {}
            except Exception:
                continue
            slug = fm.get("slug", sf.stem)
            status = fm.get("status", "unknown")
            current = ' current="true"' if slug == e.current_story else ""
            lines.append(f'    <story slug="{_xml_escape(slug)}" status="{status}"{current}/>')
    lines.append("  </stories>")
    lines.append("</brm-epic>")
    return "\n".join(lines)


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
              .replace('"', "&quot;"))

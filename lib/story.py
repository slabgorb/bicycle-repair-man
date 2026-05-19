"""Story data model, parse, serialize, state transitions for BRM v0.4."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

_VALID_STATUS = ("draft", "in_progress", "blocked", "review", "done")
_REQUIRED_KEYS = (
    "schema", "slug", "title", "epic", "workflow", "repos",
    "status", "phase", "phase_history", "acceptance",
)
_SCHEMA_PREFIX = "brm-story/"
_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)\Z", re.DOTALL)


class StorySchemaError(Exception):
    """Raised when a story file is malformed."""


class StoryTransitionError(Exception):
    """Raised when a state transition is illegal."""


@dataclass
class Story:
    slug: str
    title: str
    epic: str
    workflow: str
    repos: list[str]
    status: str                            # see _VALID_STATUS
    phase: str | None                      # current phase / step name
    phase_history: list[dict[str, Any]] = field(default_factory=list)
    acceptance: list[dict[str, Any]] = field(default_factory=list)
    last_handoff: dict[str, Any] | None = None
    blocked_reason: str | None = None
    schema: str = "brm-story/0.4"
    body: str = ""

    def is_terminal(self) -> bool:
        return self.status == "done"


def parse_story_text(text: str) -> Story:
    m = _FM_RE.match(text)
    if not m:
        raise StorySchemaError("story file must begin with YAML frontmatter")
    try:
        doc = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise StorySchemaError(f"YAML parse error: {e}") from e
    if not isinstance(doc, dict):
        raise StorySchemaError("story frontmatter must be a mapping")
    for key in _REQUIRED_KEYS:
        if key not in doc:
            raise StorySchemaError(f"missing required field: {key}")
    schema = str(doc["schema"])
    if not schema.startswith(_SCHEMA_PREFIX):
        raise StorySchemaError(f"unsupported schema: {schema}")
    status = doc["status"]
    if status not in _VALID_STATUS:
        raise StorySchemaError(
            f"status must be one of {_VALID_STATUS}, got {status!r}"
        )
    return Story(
        slug=str(doc["slug"]),
        title=str(doc["title"]),
        epic=str(doc["epic"]),
        workflow=str(doc["workflow"]),
        repos=list(doc["repos"]),
        status=status,
        phase=doc.get("phase"),
        phase_history=list(doc.get("phase_history") or []),
        acceptance=list(doc.get("acceptance") or []),
        last_handoff=doc.get("last_handoff"),
        blocked_reason=doc.get("blocked_reason"),
        schema=schema,
        body=m.group(2).lstrip("\n"),
    )


def render_story_block(s: "Story", *, path: "Path") -> str:
    """Render the <brm-story> XML block."""
    from pathlib import Path as _Path

    def esc(x: str) -> str:
        return (x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                 .replace('"', "&quot;"))
    lines = ["<brm-story>"]
    lines.append(f"  <slug>{esc(s.slug)}</slug>")
    lines.append(f"  <title>{esc(s.title)}</title>")
    lines.append(f"  <workflow>{esc(s.workflow)}</workflow>")
    lines.append(f"  <phase>{esc(s.phase or '-')}</phase>")
    lines.append(f"  <status>{s.status}</status>")
    lines.append(f"  <repos>{','.join(esc(r) for r in s.repos)}</repos>")
    if s.acceptance:
        lines.append("  <acceptance>")
        for ac in s.acceptance:
            done = "true" if ac.get("done") else "false"
            lines.append(f'    <criterion done="{done}">{esc(ac["text"])}</criterion>')
        lines.append("  </acceptance>")
    if s.last_handoff:
        h = s.last_handoff
        body = esc(h.get("body", "").strip())
        lines.append(
            f'  <last-handoff from="{esc(h.get("from",""))}" '
            f'to="{esc(h.get("to",""))}" at="{esc(h.get("at",""))}">'
        )
        lines.append(f"    {body}")
        lines.append("  </last-handoff>")
    if s.blocked_reason:
        lines.append(f"  <blocked-reason>{esc(s.blocked_reason)}</blocked-reason>")
    lines.append(f"  <path>{esc(str(path))}</path>")
    lines.append("</brm-story>")
    return "\n".join(lines)


def serialize_story(s: Story) -> str:
    fm: dict[str, Any] = {
        "schema": s.schema,
        "slug": s.slug,
        "title": s.title,
        "epic": s.epic,
        "workflow": s.workflow,
        "repos": list(s.repos),
        "status": s.status,
        "phase": s.phase,
        "phase_history": list(s.phase_history),
        "acceptance": list(s.acceptance),
    }
    if s.last_handoff is not None:
        fm["last_handoff"] = s.last_handoff
    if s.blocked_reason is not None:
        fm["blocked_reason"] = s.blocked_reason
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + s.body

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

"""Design file parse, serialize, and state transitions for BRM v0.3."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

import yaml

_VALID_DESIGN_STATUS = ("planned", "in-progress", "blocked", "complete", "abandoned")
_VALID_PHASE_STATUS = ("planned", "in-progress", "complete", "failed")
_VALID_GATE_RESULT = ("pass", "fail", "skip", None)
_REQUIRED_FRONTMATTER_KEYS = (
    "design", "created", "workflow", "repos", "status",
    "current_phase", "phases", "history",
)


class DesignSchemaError(Exception):
    """Raised when a design file is malformed or violates the schema."""


@dataclass
class Phase:
    name: str
    status: str
    started: str | None
    finished: str | None
    handoff: str | None
    gate_result: str | None
    repo: str | None = None
    repos: list[str] | None = None


@dataclass
class Design:
    design: str
    created: str
    workflow: str
    repos: list[str]
    status: str
    current_phase: str
    phases: list[Phase]
    history: list[dict[str, Any]]
    description: str = ""
    body: str = ""

    def phase(self, name: str) -> Phase:
        for p in self.phases:
            if p.name == name:
                return p
        raise DesignSchemaError(f"phase '{name}' not in design")

    def current(self) -> Phase:
        return self.phase(self.current_phase)


def parse_design_text(text: str) -> Design:
    fm_text, body = _split_frontmatter(text)
    try:
        doc = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        raise DesignSchemaError(f"YAML parse error in frontmatter: {e}") from e
    if not isinstance(doc, dict):
        raise DesignSchemaError("frontmatter must be a YAML mapping")

    for key in _REQUIRED_FRONTMATTER_KEYS:
        if key not in doc:
            raise DesignSchemaError(f"frontmatter missing required field: {key}")

    if doc["status"] not in _VALID_DESIGN_STATUS:
        raise DesignSchemaError(
            f"status must be one of {_VALID_DESIGN_STATUS}, got '{doc['status']}'"
        )
    if not isinstance(doc["repos"], list) or not doc["repos"]:
        raise DesignSchemaError("repos must be a non-empty list of short-names")

    if not isinstance(doc["phases"], list):
        raise DesignSchemaError("phases must be a list")
    phases = [_parse_phase(p) for p in doc["phases"]]
    if not any(p.name == doc["current_phase"] for p in phases):
        raise DesignSchemaError(
            f"current_phase '{doc['current_phase']}' is not in phases[]"
        )

    history = doc["history"] or []
    if not isinstance(history, list):
        raise DesignSchemaError("history must be a list")

    return Design(
        design=doc["design"],
        created=doc["created"],
        workflow=doc["workflow"],
        repos=list(doc["repos"]),
        description=doc.get("description", "") or "",
        status=doc["status"],
        current_phase=doc["current_phase"],
        phases=phases,
        history=history,
        body=body,
    )


def _parse_phase(raw: dict[str, Any]) -> Phase:
    if not isinstance(raw, dict):
        raise DesignSchemaError(f"phase entry must be a mapping, got {type(raw).__name__}")
    for key in ("name", "status", "started", "finished", "handoff", "gate_result"):
        if key not in raw:
            raise DesignSchemaError(f"phase '{raw.get('name', '?')}' missing field: {key}")
    if raw["status"] not in _VALID_PHASE_STATUS:
        raise DesignSchemaError(
            f"phase '{raw['name']}' status invalid: {raw['status']}"
        )
    if raw["gate_result"] not in _VALID_GATE_RESULT:
        raise DesignSchemaError(
            f"phase '{raw['name']}' gate_result invalid: {raw['gate_result']}"
        )
    has_repo = "repo" in raw and raw["repo"] is not None
    has_repos = "repos" in raw and raw["repos"] is not None
    if has_repo and has_repos:
        raise DesignSchemaError(
            f"phase '{raw['name']}' has both repo and repos (mutually exclusive)"
        )
    return Phase(
        name=raw["name"],
        status=raw["status"],
        started=raw["started"],
        finished=raw["finished"],
        handoff=raw["handoff"],
        gate_result=raw["gate_result"],
        repo=raw.get("repo"),
        repos=list(raw["repos"]) if has_repos else None,
    )


_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise DesignSchemaError(
            "design file must begin with a YAML frontmatter block delimited by '---'"
        )
    return m.group(1), m.group(2)

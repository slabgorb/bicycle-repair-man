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


class DesignTransitionError(Exception):
    """Raised when a state transition is illegal."""


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


def serialize_design(d: Design) -> str:
    """Round-trip-safe serialization. Frontmatter is YAML; body is verbatim."""
    fm = {
        "design": d.design,
        "created": d.created,
        "workflow": d.workflow,
        "repos": d.repos,
        "description": d.description,
        "status": d.status,
        "current_phase": d.current_phase,
        "phases": [_phase_to_dict(p) for p in d.phases],
        "history": d.history,
    }
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{fm_text}---\n{d.body}"


def _phase_to_dict(p: Phase) -> dict[str, Any]:
    out: dict[str, Any] = {"name": p.name}
    if p.repo is not None:
        out["repo"] = p.repo
    if p.repos is not None:
        out["repos"] = p.repos
    out.update({
        "status": p.status,
        "started": p.started,
        "finished": p.finished,
        "handoff": p.handoff,
        "gate_result": p.gate_result,
    })
    return out


def start_phase(d: Design, name: str, *, actor: str, at: str) -> Design:
    p = d.phase(name)
    if p.status != "planned":
        raise DesignTransitionError(f"phase '{name}' must be planned, is {p.status}")
    p.status = "in-progress"
    p.started = at
    if d.status == "planned":
        d.status = "in-progress"
    d.history.append({"at": at, "event": "phase-start", "phase": name, "actor": actor})
    return d


def record_gate_pass(d: Design, *, gate: str, at: str, actor: str) -> Design:
    p = d.current()
    p.gate_result = "pass"
    d.history.append({
        "at": at, "event": "gate-pass", "phase": p.name, "gate": gate, "actor": actor,
    })
    return d


def record_gate_fail(d: Design, *, gate: str, at: str, actor: str) -> Design:
    p = d.current()
    p.gate_result = "fail"
    d.history.append({
        "at": at, "event": "gate-fail", "phase": p.name, "gate": gate, "actor": actor,
    })
    return d


def advance_phase(d: Design, *, to: str, at: str, force: bool = False) -> Design:
    cur = d.current()
    if to == d.current_phase:
        raise DesignTransitionError(
            f"cannot advance to current phase '{to}'"
        )
    if cur.status != "in-progress":
        raise DesignTransitionError(
            f"cannot advance from '{cur.name}': status is {cur.status}, not in-progress"
        )
    if not force and cur.gate_result not in ("pass", "skip"):
        raise DesignTransitionError(
            f"cannot advance from '{cur.name}': gate_result is {cur.gate_result}"
        )
    nxt = d.phase(to)  # raises if not present
    cur.status = "complete"
    cur.finished = at
    nxt.status = "in-progress"
    nxt.started = at
    d.current_phase = to
    event = "phase-skip" if force else "phase-advance"
    d.history.append({"at": at, "event": event, "from": cur.name, "to": to})
    return d


def block_design(d: Design, *, reason: str, at: str) -> Design:
    d.status = "blocked"
    d.history.append({"at": at, "event": "block", "reason": reason})
    return d


def unblock_design(d: Design, *, at: str) -> Design:
    d.status = "in-progress"
    d.history.append({"at": at, "event": "unblock"})
    return d


def mark_complete(d: Design, *, at: str) -> Design:
    for p in d.phases:
        if p.status != "complete":
            raise DesignTransitionError(
                f"phase '{p.name}' is not complete; cannot mark design complete"
            )
    d.status = "complete"
    d.history.append({"at": at, "event": "complete"})
    return d


def mark_abandoned(d: Design, *, reason: str, at: str) -> Design:
    d.status = "abandoned"
    d.history.append({"at": at, "event": "abandon", "reason": reason})
    return d

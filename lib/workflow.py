"""Workflow YAML load + validate for BRM v0.3."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_VALID_AGENTS = ("tea", "dev", "reviewer", "architect", "pm", "tech-writer")
_VALID_EXPANSIONS = ("per-repo",)  # as-written and manual reserved for v0.4+
_RESERVED_EXPANSIONS = ("as-written", "manual")


class WorkflowSchemaError(Exception):
    """Raised when a workflow YAML is malformed or invalid."""


@dataclass
class WorkflowGate:
    file: str
    condition: str = ""


@dataclass
class WorkflowPhase:
    name: str
    agent: str
    repo: str | None = None        # short-name or "$each" sentinel
    repos: Any = None              # list[str] or "$all" sentinel
    gate: WorkflowGate | None = None
    next: str | None = None


@dataclass
class Workflow:
    name: str
    phases: list[WorkflowPhase]
    description: str = ""
    version: str = ""
    expansion: str = "per-repo"


def load_workflow(
    name: str, *, plugin_root: Path, orchestrator_root: Path | None = None,
) -> Workflow:
    for candidate in _candidates(name, plugin_root, orchestrator_root):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8")
            return _parse_workflow(text)
    raise WorkflowSchemaError(f"workflow '{name}' not found in any search path")


def _candidates(name: str, plugin_root: Path, orchestrator_root: Path | None):
    if orchestrator_root is not None:
        yield orchestrator_root / ".brm" / "workflows" / f"{name}.yaml"
    yield plugin_root / "workflows" / f"{name}.yaml"


def _parse_workflow(text: str) -> Workflow:
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise WorkflowSchemaError(f"YAML parse error: {e}") from e
    if not isinstance(doc, dict) or "workflow" not in doc:
        raise WorkflowSchemaError("workflow file must have a top-level 'workflow' key")
    wf = doc["workflow"]

    expansion = wf.get("expansion", "per-repo")
    if expansion in _RESERVED_EXPANSIONS:
        raise WorkflowSchemaError(
            f"expansion '{expansion}' is reserved for v0.4+"
        )
    if expansion not in _VALID_EXPANSIONS:
        raise WorkflowSchemaError(f"unknown expansion '{expansion}'")

    phases_raw = wf.get("phases") or []
    if not phases_raw:
        raise WorkflowSchemaError("workflow must have at least one phase")
    phases = [_parse_phase(p) for p in phases_raw]

    seen: set[str] = set()
    for p in phases:
        if p.name in seen:
            raise WorkflowSchemaError(f"duplicate phase name: {p.name}")
        seen.add(p.name)

    out = Workflow(
        name=wf.get("name", ""),
        description=wf.get("description", "") or "",
        version=wf.get("version", "") or "",
        expansion=expansion,
        phases=phases,
    )
    validate_workflow(out)
    return out


def _parse_phase(raw: dict[str, Any]) -> WorkflowPhase:
    if not isinstance(raw, dict) or "name" not in raw or "agent" not in raw:
        raise WorkflowSchemaError(f"phase missing name/agent: {raw!r}")
    if raw["agent"] not in _VALID_AGENTS:
        raise WorkflowSchemaError(
            f"phase '{raw['name']}': agent '{raw['agent']}' not in {_VALID_AGENTS}"
        )
    has_repo = "repo" in raw and raw["repo"] is not None
    has_repos = "repos" in raw and raw["repos"] is not None
    if has_repo and has_repos:
        raise WorkflowSchemaError(
            f"phase '{raw['name']}': repo and repos are mutually exclusive"
        )
    if has_repos and raw["repos"] == "$each":
        raise WorkflowSchemaError(
            f"phase '{raw['name']}': $each is only valid on 'repo:'"
        )
    if has_repo and raw["repo"] == "$all":
        raise WorkflowSchemaError(
            f"phase '{raw['name']}': $all is only valid on 'repos:'"
        )
    gate = None
    if "gate" in raw and raw["gate"]:
        g = raw["gate"]
        if not isinstance(g, dict) or "file" not in g:
            raise WorkflowSchemaError(
                f"phase '{raw['name']}': gate must be a mapping with 'file'"
            )
        gate = WorkflowGate(file=g["file"], condition=g.get("condition", "") or "")
    return WorkflowPhase(
        name=raw["name"], agent=raw["agent"],
        repo=raw.get("repo"),
        repos=raw["repos"] if has_repos else None,
        gate=gate,
        next=raw.get("next"),
    )


def validate_workflow(wf: Workflow) -> None:
    names = {p.name for p in wf.phases}
    for p in wf.phases:
        if p.next is not None and p.next not in names:
            raise WorkflowSchemaError(
                f"phase '{p.name}': next '{p.next}' is not a phase name"
            )


def expand_phases(wf: Workflow, repos: list[str]) -> list[WorkflowPhase]:
    """Resolve $each / $all sentinels against the design's repos list."""
    if not repos:
        raise WorkflowSchemaError("cannot expand: repos list is empty")

    out: list[WorkflowPhase] = []
    for p in wf.phases:
        if p.repo == "$each":
            for r in repos:
                out.append(WorkflowPhase(
                    name=f"{p.name}-{r}",
                    agent=p.agent,
                    repo=r,
                    repos=None,
                    gate=p.gate,
                    next=None,    # explicit next is dropped under $each expansion
                ))
        elif p.repos == "$all":
            out.append(WorkflowPhase(
                name=p.name,
                agent=p.agent,
                repo=None,
                repos=list(repos),
                gate=p.gate,
                next=p.next,
            ))
        else:
            out.append(WorkflowPhase(
                name=p.name,
                agent=p.agent,
                repo=p.repo,
                repos=list(p.repos) if p.repos else None,
                gate=p.gate,
                next=p.next,
            ))
    return out

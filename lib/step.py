"""Step-file parser (5-tag XML schema) for stepped workflows."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_TAG_RE = lambda tag: re.compile(rf"<{tag}>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE)


class StepSchemaError(Exception):
    pass


@dataclass
class Step:
    number: int
    name: str
    gate: bool = False
    next: str | None = None
    repo: str | None = None
    skill: str | None = None
    requires_skill: bool = False
    purpose: str = ""
    instructions: str = ""
    output: str = ""
    gate_text: str | None = None
    path: Path | None = None


def parse_step_text(text: str) -> Step:
    meta_m = _TAG_RE("step-meta").search(text)
    if not meta_m:
        raise StepSchemaError("step file missing <step-meta> section")
    try:
        meta = yaml.safe_load(meta_m.group(1))
    except yaml.YAMLError as e:
        raise StepSchemaError(f"<step-meta> YAML error: {e}") from e
    if not isinstance(meta, dict) or "number" not in meta or "name" not in meta:
        raise StepSchemaError("<step-meta> must include number and name")

    def grab(tag: str) -> str:
        m = _TAG_RE(tag).search(text)
        return m.group(1).strip() if m else ""

    return Step(
        number=int(meta["number"]),
        name=str(meta["name"]),
        gate=bool(meta.get("gate", False)),
        next=meta.get("next"),
        repo=meta.get("repo"),
        skill=meta.get("skill"),
        requires_skill=bool(meta.get("requires_skill", False)),
        purpose=grab("purpose"),
        instructions=grab("instructions"),
        output=grab("output"),
        gate_text=grab("gate") or None,
    )


def load_steps_dir(steps_dir: Path) -> list[Step]:
    """Load all step-NN-*.md files in order by `number`."""
    if not steps_dir.is_dir():
        raise StepSchemaError(f"steps directory not found: {steps_dir}")
    steps: list[Step] = []
    for p in sorted(steps_dir.glob("step-*.md")):
        s = parse_step_text(p.read_text())
        s.path = p
        steps.append(s)
    steps.sort(key=lambda s: s.number)
    return steps

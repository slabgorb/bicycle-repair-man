"""Gate file parse, prompt template, and GATE_RESULT validate."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_VALID_RESULT_STATUS = ("pass", "fail")


class GateResultError(Exception):
    """Raised when a gate file or GATE_RESULT is malformed."""


@dataclass
class Gate:
    name: str
    model: str
    text: str    # raw gate file text, with template tokens unresolved


@dataclass
class GateContext:
    design_path: str
    workflow: str
    current_phase: str
    phase_name: str
    phase_repo: str | None
    repo_name: str | None
    repo_path: str | None


_GATE_OPEN_RE = re.compile(r'<gate\s+name="([^"]+)"(?:\s+model="([^"]+)")?\s*>')


def parse_gate_file(path: Path) -> Gate:
    text = path.read_text(encoding="utf-8")
    m = _GATE_OPEN_RE.search(text)
    if not m:
        raise GateResultError(f"<gate> tag not found in {path}")
    return Gate(name=m.group(1), model=m.group(2) or "haiku", text=text)


def render_gate_prompt(gate: Gate, ctx: GateContext) -> str:
    body = gate.text
    subs = {
        "design.path": ctx.design_path,
        "phase.name": ctx.phase_name,
        "phase.repo": ctx.phase_repo or "",
        "repo.path": ctx.repo_path or "",
        "repo.name": ctx.repo_name or "",
        "workflow": ctx.workflow,
    }
    for key, val in subs.items():
        body = body.replace(f"${{{key}}}", val)

    ctx_block_parts = [
        f'<design path="{ctx.design_path}" workflow="{ctx.workflow}" '
        f'current-phase="{ctx.current_phase}"/>',
    ]
    if ctx.phase_repo:
        ctx_block_parts.append(
            f'<phase name="{ctx.phase_name}" repo="{ctx.phase_repo}"/>'
        )
    else:
        ctx_block_parts.append(f'<phase name="{ctx.phase_name}"/>')
    if ctx.repo_name and ctx.repo_path:
        ctx_block_parts.append(
            f'<repo name="{ctx.repo_name}" path="{ctx.repo_path}"/>'
        )

    ctx_block = "<gate-context>\n  " + "\n  ".join(ctx_block_parts) + "\n</gate-context>"
    return f"{ctx_block}\n\n{body}"


_RESULT_RE = re.compile(r"GATE_RESULT:\s*\n((?:  .*\n?)+)", re.MULTILINE)


def parse_gate_result(text: str) -> dict:
    m = _RESULT_RE.search(text)
    if not m:
        raise GateResultError("GATE_RESULT block not found in subagent output")
    block = "GATE_RESULT:\n" + m.group(1)
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as e:
        raise GateResultError(f"GATE_RESULT YAML invalid: {e}") from e
    if not isinstance(parsed, dict) or "GATE_RESULT" not in parsed:
        raise GateResultError("GATE_RESULT block did not parse to a mapping")
    inner = parsed["GATE_RESULT"]
    if not isinstance(inner, dict):
        raise GateResultError("GATE_RESULT must be a mapping")
    if inner.get("status") not in _VALID_RESULT_STATUS:
        raise GateResultError(
            f"GATE_RESULT.status must be one of {_VALID_RESULT_STATUS}, "
            f"got {inner.get('status')!r}"
        )
    return inner

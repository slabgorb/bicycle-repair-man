"""Agent definition parser and discovery for BRM v0.4."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_VALID_KINDS = ("strategic", "tactical", "helper")
_TAG_RE = lambda tag: re.compile(rf"<{tag}>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE)
_KIND_RE = re.compile(r"\*\*Kind:\*\*\s*(\w[\w-]*)", re.IGNORECASE)
_ANCHOR_RE = re.compile(r"Anchor skill[^:]*:\s*\*{0,2}\s*`([^`\n]+)`", re.IGNORECASE)
_HELPER_BULLET_RE = re.compile(r"^\s*[-*]\s+`?([^\s`]+)`?", re.MULTILINE)


class AgentSchemaError(Exception):
    """Raised when an agent file is malformed."""


@dataclass
class Agent:
    name: str
    kind: str                        # strategic | tactical | helper
    title: str = ""
    persona: str = ""
    role: str = ""
    helpers: list[str] = field(default_factory=list)
    responsibilities: str = ""
    skills: str = ""
    anchor_skill: str | None = None
    constraints: str = ""
    context: str = ""
    on_activation: str = ""
    handoff: str = ""
    exit_section: str = ""
    body: str = ""
    path: Path | None = None


def parse_agent_text(text: str, *, name: str) -> Agent:
    def grab(tag: str, required: bool = False) -> str:
        m = _TAG_RE(tag).search(text)
        if not m:
            if required:
                raise AgentSchemaError(f"agent '{name}': missing <{tag}> section")
            return ""
        return m.group(1).strip()

    role_section = grab("role", required=True)
    km = _KIND_RE.search(role_section)
    if not km:
        raise AgentSchemaError(f"agent '{name}': <role> must declare **Kind:** strategic|tactical|helper")
    kind = km.group(1).lower()
    if kind not in _VALID_KINDS:
        raise AgentSchemaError(
            f"agent '{name}': kind must be one of {_VALID_KINDS}, got '{kind}'"
        )

    helpers_section = grab("helpers")
    helpers = _HELPER_BULLET_RE.findall(helpers_section) if helpers_section else []

    skills_section = grab("skills")
    anchor_match = _ANCHOR_RE.search(skills_section) if skills_section else None
    anchor_skill = anchor_match.group(1).strip().strip("`") if anchor_match else None

    # Title: first H1
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return Agent(
        name=name,
        kind=kind,
        title=title,
        persona=grab("persona"),
        role=role_section,
        helpers=helpers,
        responsibilities=grab("responsibilities"),
        skills=skills_section,
        anchor_skill=anchor_skill,
        constraints=grab("constraints"),
        context=grab("context"),
        on_activation=grab("on-activation"),
        handoff=grab("handoff"),
        exit_section=grab("exit"),
        body=text,
    )


def discover_agents(
    plugin_root: Path,
    *,
    cwd: Path | None = None,
    orchestrator_root: Path | None = None,
    project_root: Path | None = None,
    global_root: Path | None = None,
) -> dict[str, Agent]:
    """Discover all agents from layered paths. Higher priority shadows lower.

    Order (highest -> lowest):
      1. orchestrator/.brm/agents/
      2. project/.brm/agents/
      3. global/~/.brm/agents/  (default: ~/.brm/agents/)
      4. plugin/agents/         (built-ins)
    """
    cwd = cwd or Path.cwd()
    global_root = global_root or (Path.home() / ".brm" / "agents")
    found: dict[str, Agent] = {}

    def _scan(root: Path):
        if not root.is_dir():
            return
        for p in sorted(root.glob("*.md")):
            name = p.stem
            if name in found:
                continue  # already shadowed by higher-priority scope
            try:
                a = parse_agent_text(p.read_text(), name=name)
            except AgentSchemaError:
                continue
            a.path = p
            found[name] = a

    if orchestrator_root is not None:
        _scan(orchestrator_root / ".brm" / "agents")
    if project_root is not None:
        _scan(project_root / ".brm" / "agents")
    _scan(global_root)
    _scan(plugin_root / "agents")
    return found

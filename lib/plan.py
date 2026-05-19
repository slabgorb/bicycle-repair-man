"""Plan-document parser for BRM v0.4.

Plans are markdown files with `## Story: <title>` H2 headers. Each header is
followed (after optional blank lines) by a fenced YAML block declaring the
story's frontmatter (slug, optional workflow/repos/acceptance). The content
between the YAML fence and the next `## Story:` header (or EOF) is the story
body.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_STORY_HEADER_RE = re.compile(r"^##\s+Story:\s*(.+?)\s*$", re.MULTILINE)
_YAML_FENCE_RE = re.compile(r"^```(?:yaml|yml)?\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


class PlanParseError(Exception):
    """Raised when a plan file cannot be parsed."""


@dataclass
class PlanStory:
    slug: str
    title: str
    workflow: str | None = None
    repos: list[str] | None = None
    acceptance: list[str] = field(default_factory=list)
    body: str = ""
    line: int = 0  # line of the `## Story:` header (1-based)


@dataclass
class Plan:
    preamble: str = ""
    stories: list[PlanStory] = field(default_factory=list)


def parse_plan_text(text: str) -> Plan:
    headers = list(_STORY_HEADER_RE.finditer(text))
    if not headers:
        return Plan(preamble=text.rstrip() + "\n", stories=[])

    preamble = text[: headers[0].start()].rstrip()
    if preamble:
        preamble += "\n"

    plan = Plan(preamble=preamble)
    seen_slugs: dict[str, int] = {}

    for i, header in enumerate(headers):
        title = header.group(1).strip()
        header_line = text[: header.start()].count("\n") + 1
        next_start = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[header.end():next_start]

        fence_match = _YAML_FENCE_RE.search(block)
        if not fence_match:
            raise PlanParseError(
                f"line {header_line}: '## Story: {title}' is not followed by a YAML fence"
            )

        try:
            fence_doc = yaml.safe_load(fence_match.group(1))
        except yaml.YAMLError as e:
            raise PlanParseError(
                f"line {header_line}: malformed YAML in story fence: {e}"
            ) from e
        if not isinstance(fence_doc, dict):
            raise PlanParseError(
                f"line {header_line}: YAML fence must be a mapping"
            )

        if "slug" not in fence_doc:
            raise PlanParseError(f"line {header_line}: missing slug in YAML fence")
        slug = str(fence_doc["slug"])
        if not _SLUG_RE.match(slug):
            raise PlanParseError(
                f"line {header_line}: slug must match {_SLUG_RE.pattern}, got '{slug}'"
            )
        if slug in seen_slugs:
            raise PlanParseError(
                f"duplicate slug '{slug}' at lines {seen_slugs[slug]} and {header_line}"
            )
        seen_slugs[slug] = header_line

        body = block[fence_match.end():].strip("\n")

        story = PlanStory(
            slug=slug,
            title=title,
            workflow=fence_doc.get("workflow"),
            repos=list(fence_doc["repos"]) if "repos" in fence_doc else None,
            acceptance=list(fence_doc.get("acceptance", [])),
            body=body,
            line=header_line,
        )
        plan.stories.append(story)

    return plan

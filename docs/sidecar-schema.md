# BRM sidecar schema

This document specifies the on-disk format of BRM sidecars — the per-role
persistent memory files BRM injects on role activation.

## Layers

A role has up to two sidecar files:

| Layer | Path | Purpose |
|---|---|---|
| Global | `~/.claude/brm/sidecars/<role>.md` | Lessons that follow you across projects. |
| Project | `<project_root>/.brm/sidecars/<role>.md` | Lessons specific to this codebase. |

`<project_root>` is the nearest ancestor of the current directory that
contains a `.git` (file or directory) or `.brm/` directory, with a 20-level
walk cap. If no project root is found, only the global layer can contribute.

Project files do not override the global file; both layers contribute. The
hook injects the global layer first, then the project layer, so newer
project-specific knowledge appears last in the model's context.

## File format

Each sidecar is plain Markdown with three required H2 sections:

```markdown
# <Role> sidecar

## Patterns
- 2026-05-12 — Tests-first reviews catch ~3x more issues than tests-after.

## Gotchas
- 2026-05-10 — Async fixtures in pytest-asyncio v0.23 swallow errors silently
  unless `asyncio_mode = "strict"` is set.

## Decisions
- 2026-05-09 — Don't flag missing type hints unless the function is exported.
```

Rules:

- Entries are bullets.
- Each entry begins with an ISO-8601 date (`YYYY-MM-DD`) followed by an em-dash.
- Newest entries at the top of each section.
- Roles may add additional H2 sections at their own risk; the hook injects
  the entire file verbatim and does not validate structure.

## Injection format

When a role command (`/<role>` or `/brm:<role>`) is the leading token of a
user prompt, the hook emits:

```
<brm-sidecar role="<role>">
  <layer scope="global" path="~/.claude/brm/sidecars/<role>.md">
<file contents verbatim>
  </layer>
  <layer scope="project" path=".brm/sidecars/<role>.md">
<file contents verbatim>
  </layer>
</brm-sidecar>
```

Layers that don't exist or are unreadable are silently skipped. If neither
layer contributes, the hook emits no `additionalContext` at all.

## Writing to sidecars

The sidecar is written *conversationally*. When the user says "add that to
your sidecar" (or equivalent), the active role appends a bullet to the
appropriate section, ISO-dated, newest-first. The role brief specifies the
exact path and format.

BRM does not ship a CLI for sidecar management. Edit the files directly when
needed.

## Deliberately not in v1

- Size capping or trimming.
- Cross-role / shared / "team" sidecars.
- Schema validation beyond the H2 section names.
- A `/brm:sidecar` management command.

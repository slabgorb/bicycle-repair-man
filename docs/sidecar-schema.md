# BRM sidecar schema

This document specifies the on-disk format of BRM sidecars — the per-role
persistent memory files BRM injects on role activation.

## Layers

A role has up to three sidecar files. Layers are emitted in order from
**most general** to **most specific**, so the most specific lessons appear
last (and are most salient to the model).

| Layer | Path | Purpose |
|---|---|---|
| Global | `~/.claude/brm/sidecars/<role>.md` | Lessons that follow you across projects. |
| Orchestrator | `<orchestrator_root>/.brm/sidecars/<role>.md` | Lessons specific to a multi-repo workspace. Only present when an orchestrator root is detected (`.brm/repos.yaml` exists in some ancestor of cwd). |
| Project | `<project_root>/.brm/sidecars/<role>.md` | Lessons specific to a single repo. |

`<orchestrator_root>` is the nearest ancestor of the current directory whose
`.brm/repos.yaml` is a regular file, with a 20-level walk cap. See
`docs/orchestrator-schema.md` for the orchestrator config schema.

`<project_root>` is the nearest ancestor of the current directory that
contains `.git` (file or directory) or `.brm/sidecars/` (directory), with a
20-level walk cap. Note: a bare `.brm/` directory is NOT a project-root
marker — it may indicate an orchestrator root instead.

If no orchestrator root is found, only global + project layers can
contribute (v0.1.0 behavior). If neither orchestrator nor project root is
found, only the global layer can contribute.

No layer overrides any other; all available layers concatenate.

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
  <layer scope="orchestrator" path=".brm/sidecars/<role>.md">
<file contents verbatim>
  </layer>
  <layer scope="project" path=".brm/sidecars/<role>.md">
<file contents verbatim>
  </layer>
</brm-sidecar>
```

Layers that don't exist or are unreadable are silently skipped. If no layer
contributes, the hook emits no `<brm-sidecar>` block at all.

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

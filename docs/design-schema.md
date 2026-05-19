# BRM Design Schema

This document describes the on-disk format of BRM v0.3 designs, workflows,
and gates. For the rationale and architectural decisions, see the spec at
`docs/superpowers/specs/2026-05-12-brm-v0.3-cross-repo-workflows-design.md`.

## Designs

A **design** is the runtime state of a piece of work spanning one or more
repos. It is a markdown file with YAML frontmatter at
`docs/superpowers/designs/YYYY-MM-DD-<slug>.md`.

### Frontmatter

| Field | Type | Required | Notes |
|---|---|---|---|
| `design` | string | yes | Slug; must equal filename stem |
| `created` | ISO 8601 | yes | Set at init; never modified |
| `workflow` | string | yes | Resolves to `<orchestrator>/.brm/workflows/<name>.yaml` then `<plugin_root>/workflows/<name>.yaml` |
| `repos` | string list | yes | Non-empty subset of `repos.yaml` keys |
| `description` | string | no | One-liner |
| `status` | enum | yes | `planned | in-progress | blocked | complete | abandoned` |
| `current_phase` | string | yes (after init) | Matches a `phases[].name` |
| `phases[]` | list | yes | Mirrors workflow phase list after `$each` / `$all` expansion |
| `phases[].name` | string | yes | Unique within design |
| `phases[].repo` | string | xor `repos` | Single short-name |
| `phases[].repos` | string list | xor `repo` | Multi-repo phase |
| `phases[].status` | enum | yes | `planned | in-progress | complete | failed` |
| `phases[].started` | ISO 8601 or null | yes | |
| `phases[].finished` | ISO 8601 or null | yes | |
| `phases[].handoff` | string or null | yes | Anchor like `"#handoffs/red-api"` |
| `phases[].gate_result` | enum or null | yes | `pass | fail | skip | null` |
| `history[]` | append-only list | yes | Audit trail; written only by `brm-design` |

### Handoff block format

A handoff is XML in the body, inside `## Handoffs`, under a heading whose
anchor matches the `phases[<name>].handoff` value:

```xml
<handoff from="<phase>" to="<phase>" repo="<short-name>" agent="<role>" at="<ISO 8601>">
Summary: <2-3 sentences>
Deliverables:
  - <path>: <what changed>
Test status: failing=<N> passing=<N> skipped=<N>
Key decisions:
  - <decision>: <rationale>
Open questions:
  - <question>
</handoff>
```

## Workflows

Workflow YAML files live at `<plugin_root>/workflows/<name>.yaml` (built-in)
or `<orchestrator>/.brm/workflows/<name>.yaml` (override).

See `lib/workflow.py` and the spec for the full schema. Key fields:

- `name`, `description`, `version`, `expansion: per-repo`
- `phases[]`: each phase has `name`, `agent` (one of the six BRM roles),
  optional `repo` (single short-name, or `$each` for init-time expansion) or
  `repos` (list, or `$all` for the design's repos), optional `gate.file`,
  optional `next`.

Built-in workflows: `tdd`, `patch`, `docs`, `architecture`.

## Gates

Gate files at `<plugin_root>/gates/<name>.md` (built-in) or
`<orchestrator>/.brm/gates/<name>.md` (override). PF-shaped markdown + XML
with a `GATE_RESULT` YAML contract. The plugin substitutes `${design.path}`,
`${phase.name}`, `${phase.repo}`, `${repo.path}`, `${repo.name}`, and
`${workflow}` before the prompt is rendered.

Built-in gates: `tests-fail`, `tests-pass`, `quality-pass`, `approval`,
`design-complete`.

## CLI cheat sheet

```bash
# Create
brm-design init <slug> --workflow tdd --repos api,ui

# Inspect
brm-design status            # auto-finds the active design
brm-design status --json
brm-design list --status in-progress

# Drive the workflow
brm-design handoff <path> --from red-api --to green-api --stdin <h.xml
brm-design gate <path>       # emits the prompt
brm-design record-gate <path> --result-stdin <result.txt
brm-design advance <path> --to green-api

# Lifecycle
brm-design block <path> --reason "<one-liner>"
brm-design unblock <path>
brm-design complete <path>
brm-design abandon <path> --reason "<one-liner>"

# Maintenance
brm-design validate <path>
```

All subcommands invoked via `${CLAUDE_PLUGIN_ROOT}/scripts/brm-design`.

## Environment

- `BRM_ACTIVE_DESIGN` — explicit design path (bypasses discovery).
- `BRM_DESIGNS_DIR` — search root override (default: `<orchestrator>/docs/superpowers/designs/` or `<repo>/docs/superpowers/designs/`).
- v0.2 env vars (`BRM_HOME`, `BRM_PROJECT_ROOT`, `BRM_ORCHESTRATOR_ROOT`) still apply.

---

## Epic frontmatter (v0.4)

Epics replace the single-design file as the top-level work container. Frontmatter schema (YAML):

```yaml
schema: brm-epic/0.4              # required
slug: 2026-05-19-foo              # required, kebab-case
title: Foo                        # required
status: draft                     # required; draft | active | done
workflow: tdd                     # required; default workflow for stories
repos: [brm]                      # required; list of repo short-names
created: 2026-05-19               # required; ISO date
current_story: 02-bar             # optional; hook reads this for <brm-story>
spec_approval:                    # optional; gate on draft → active
  required: true
  approved_at: 2026-05-19T14:22:00Z
  approver: keith
```

The body (after the closing `---`) is free-form markdown — typically the
brainstorm output (the spec body).

## Story frontmatter (v0.4)

Stories live at `<epic>/stories/<slug>.md`. They are created by
`brm story split` from the plan's `## Story:` markers.

```yaml
schema: brm-story/0.4             # required
slug: 01-foo                      # required
title: Foo story                  # required
epic: 2026-05-19-foo              # required (parent epic slug)
workflow: tdd                     # required (resolved: story override → epic default)
repos: [brm]                      # required (resolved similarly)
status: in_progress               # draft | in_progress | blocked | review | done
phase: green                      # current phase or step name
phase_history:                    # list of phase transitions
  - phase: red
    entered: 2026-05-19T15:10:00Z
    exited: 2026-05-19T16:42:00Z
    gate_result: pass
acceptance:                       # list of objects with done flag
  - { done: true, text: "first AC" }
  - { done: false, text: "second AC" }
last_handoff:                     # optional
  from: tea
  to: dev
  at: 2026-05-19T16:42:00Z
  body: |
    Tests are failing as expected.
blocked_reason: null              # optional; set by brm story block
```

The body contains the implementation notes (from the plan slice) plus an
appended `## Handoff log` section maintained by `brm story handoff`.

## Plan story markers (v0.4)

`plan.md` files use `## Story: <title>` H2 headers to mark story boundaries.
Each header must be followed (after optional blank lines) by a YAML fence
declaring at minimum the `slug:` field. See [`stepped-workflow-schema.md`](stepped-workflow-schema.md)
for the parallel stepped step-file pattern.

# Migration: BRM v0.3 → v0.4

v0.4 introduces epic/story hierarchy, two-file agent definitions, stepped
workflows, and a unified `brm` CLI. **No code changes are required for existing
v0.3 designs to keep working** — legacy shims preserve their behavior.

## What changed (TL;DR)

| Surface | v0.3 | v0.4 |
|---|---|---|
| Unit of work | `<project>/.brm/designs/<name>.md` (single file) | `<project>/.brm/epics/<slug>/` (folder with epic + plan + stories) |
| Workflow attachment | per-design | per-epic, per-story override allowed |
| State machine | per-design | per-story; epic has draft/active/done lifecycle |
| CLI | `brm-design <verb>`, `brm-repos <verb>` | `brm <noun> <verb>` (unified); legacy commands warn but still work |
| Role definitions | `commands/<name>.md` single file | `agents/<name>.md` (rich, XML-tagged) + `commands/<name>.md` (thin wrapper) |
| Custom agents | not supported | `.brm/agents/<name>.md` + `brm role new` |
| Workflow types | phased only | phased + stepped |
| Expansion modes | `per-repo` (only) | `per-repo` (default) + `as-written`; `manual` dropped |

## Legacy commands keep working

`scripts/brm-design` and `scripts/brm-repos` print a deprecation warning but
continue to function. Existing tests against the v0.3 CLI still pass.

`<project>/.brm/designs/<name>.md` files are read by the legacy shim. They are
NOT auto-promoted to v0.4 epics. Use them as-is until you choose to migrate.

## Manual migration (per design)

To promote a v0.3 design to a v0.4 epic:

```bash
mkdir -p .brm/epics/<slug>/stories
mv .brm/designs/<slug>.md .brm/epics/<slug>/epic.md
# Edit .brm/epics/<slug>/epic.md to add v0.4 frontmatter:
#   schema: brm-epic/0.4
#   status: active (or draft)
#   spec_approval: null (or per spec)
```

Then create a `plan.md` (the implementation plan), mark story boundaries with
`## Story:` headers, and run `brm story split <slug>` to extract story files.

## Hook behavior

The hook continues to emit `<brm-sidecar>`, `<brm-orchestrator>`, and (legacy)
`<brm-design>` blocks for v0.3 designs. It additionally emits `<brm-epic>` and
`<brm-story>` blocks when a v0.4 epic is detected. Both can coexist in a
workspace; the role briefs handle whichever blocks are present.

## Updating role briefs

If you've customized any of the six built-in role briefs, the v0.4 layout
moves persona/responsibilities/skills into `agents/<name>.md`. The
`commands/<name>.md` wrapper is intentionally minimal. Re-locate your
customizations to the agent file.

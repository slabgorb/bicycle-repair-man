# Stepped workflow schema (v0.4)

Stepped workflows are user-gated, single-agent flows. Each step lives in its
own markdown file with a 5-tag XML schema. Contrast with phased workflows
(agent-driven handoffs, auto-advance after gate-pass).

## When to use stepped vs phased

- **Phased** — multi-agent TDD-style flows with handoffs and auto-advance
  (`tdd`, `patch`, `docs`).
- **Stepped** — single-agent flows that progress one step at a time under
  user control (`architecture`, `release`, `git-cleanup`).

## Workflow YAML

```yaml
workflow:
  name: architecture
  description: Collaborative architectural decision-making.
  version: "0.4.0"
  type: stepped
  agent: architect
  steps:
    path: ./architecture/steps/
    pattern: 'step-{nn}-*.md'
  triggers:
    types: [architecture, design, adr]
    default: false
```

Required: `name`, `type: stepped`, `agent`, `steps.path`.
Forbidden on stepped workflows: `phases:`, `expansion:`.

## Step file (5 tags)

```markdown
# Step N: Title

<step-meta>
number: N
name: short-name
gate: false
next: step-(N+1)-name | null
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
What this step accomplishes.
</purpose>

<instructions>
1. First action.
2. Second action.
</instructions>

<output>
What this step produces.
</output>

<!-- Only when gate: true -->
<gate>
## Completion criteria
- [ ] Criterion 1
- [ ] Criterion 2
</gate>
```

Drop from PF's stepped schema (BMAD ceremony): `<prerequisites>`, `<actions>`,
collaboration menus, switch prompts, `after_steps` arrays.

## Advance semantics

Stepped workflows progress only via `brm story advance <epic> --to <step-name>`.
No auto-advance. The workflow's `agent:` field declares the single agent that
runs all steps.

## Override hierarchy

Step files at `<orchestrator_root>/.brm/workflows/<name>/steps/` override the
plugin's `${CLAUDE_PLUGIN_ROOT}/workflows/<name>/steps/`. The discovery is
mechanical: per-step file by name.

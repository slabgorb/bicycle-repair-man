# Agent schema (v0.4)

BRM agents follow PF's two-file pattern: a rich definition in `agents/<name>.md`
and a thin slash command wrapper in `commands/<name>.md`.

## Discovery order

The hook, CLI, and workflow validator look for an agent named `<name>` in
this order. First match wins:

1. `<orchestrator_root>/.brm/agents/<name>.md`
2. `<project_root>/.brm/agents/<name>.md`
3. `~/.brm/agents/<name>.md` (global)
4. `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` (built-in)

`brm roles list --include-custom` shows the resolved set.

## Tags

Agent definitions are markdown with XML-tagged sections. Required for all roles:

- `<role>` — must contain `**Kind:** strategic | tactical | helper`.

Standard tags (required for strategic and tactical):

| Tag | Purpose |
|---|---|
| `<persona>` | Fallback persona when Zeitgoose is not active |
| `<role>` | Kind, primary use, workflow position |
| `<helpers>` | Bullet list of Haiku-class subagents this agent may Task-dispatch |
| `<responsibilities>` | What this agent does |
| `<skills>` | Anchor skill (the line `**Anchor skill (default):** `superpowers:foo`` is parsed) |
| `<context>` | What files/paths this agent reads on activation |
| `<on-activation>` | Numbered startup steps |
| `<handoff>` | How to hand off via `brm story handoff` |
| `<exit>` | How activation ends |

Optional:

| Tag | Purpose |
|---|---|
| `<constraints>` | Explicit exclusions |
| `<reasoning-mode>` | Tactical-only; describes per-step thinking discipline |

Helpers may omit most tags — only `<role>` (with `**Kind:** helper`) and
`<on-activation>` are required.

## Strategic vs tactical

- **Strategic** roles (PM, Architect, Tech Writer) support the TDD flow but
  aren't part of the SM/TEA/Dev/Reviewer cycle. They typically anchor on
  brainstorming or writing-plans skills.
- **Tactical** roles (TEA, Dev, Reviewer) execute the TDD cycle. They anchor
  on test-driven-development, systematic-debugging, or requesting-code-review.
- **Helpers** are not user-activatable; they're Task-dispatched by other agents
  with `model: haiku`.

## Slash command wrapper

Every role command file in `commands/<name>.md` (built-in) or
`.claude/commands/<name>.md` (custom) must include:

```yaml
---
description: <one-line description>
brm-role: true
brm-agent: <name>
---
```

The `brm-role: true` flag is what the BRM hook uses to recognise the file
as a role activation; without it, the file is treated as a plain Claude Code
slash command.

The wrapper body should be thin — a few sentences pointing at the agent
definition. Do not duplicate role content; that lives in `agents/<name>.md`.

## Scaffolding a custom role

```bash
brm role new <name> --kind tactical
```

This creates:

- `.brm/agents/<name>.md` from the appropriate template
- `.claude/commands/<name>.md` (the slash command wrapper)

Edit the agent file to fill in real content. Run `brm roles list --include-custom`
to confirm discovery.

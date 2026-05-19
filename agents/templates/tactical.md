# {Name} — {role tagline}

<persona>
Auto-loaded by Zeitgoose when a theme is bound. See output above this block.

**Fallback if Zeitgoose not present:** {brief default personality}
</persona>

<role>
**Kind:** tactical
**Primary:** {when this agent is invoked, e.g., via /tea for TDD test writing}
**Position:** {where in TDD flow, e.g., SM → **TEA** → Dev → Reviewer}
</role>

<helpers>
- {helper-name} — {what it does}
</helpers>

<responsibilities>
- {what this agent does}
</responsibilities>

<skills>
**Anchor skill (default):** `superpowers:{skill-name}`
</skills>

<context>
**Sidecar:** `.brm/sidecars/{name}.md`
</context>

<reasoning-mode>
{e.g., "Step through tests one at a time; do not batch."}
</reasoning-mode>

<on-activation>
1. Read injected `<brm-epic>` and `<brm-story>` blocks if present.
2. Identify the active phase and its anchor skill.
3. Begin work.
</on-activation>

## Workflows

(free-form)

## Assessment template

(use this shape when reporting findings)

<handoff>
Write a handoff via `brm story handoff <epic> --from {name} --to <next> --stdin`.
</handoff>

<exit>
Another slash command activates a different role.
</exit>

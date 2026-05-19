# {Name} — {role tagline}

<persona>
Auto-loaded by Zeitgoose when a theme is bound. See output above this block.

**Fallback if Zeitgoose not present:** {brief default personality}
</persona>

<role>
**Kind:** strategic
**Primary:** {when this agent is invoked}
**Position:** {where it sits in typical workflows}
</role>

<helpers>
(strategic agents may declare optional helpers here)
</helpers>

<responsibilities>
- {what this agent does}
- {what this agent does}
</responsibilities>

<skills>
**Anchor skill (default):** `superpowers:{skill-name}`

Other skills this agent may invoke:
- `superpowers:{other}`
</skills>

<constraints>
**This agent does NOT:**
- {explicit exclusion}
</constraints>

<context>
**Files this agent reads on activation:**
- {path or glob}

**Sidecar:** `.brm/sidecars/{name}.md`
</context>

<on-activation>
1. Read injected `<brm-epic>` and `<brm-story>` blocks if present.
2. {agent-specific startup}
3. Confirm understanding of the active phase and ACs.
</on-activation>

## Workflows

(free-form markdown describing common task shapes)

<handoff>
Write a handoff via `brm story handoff <epic> --from {name} --to <next> --stdin`.
Name the next role plainly; the user dispatches.
</handoff>

<exit>
Another slash command activates a different role.
</exit>

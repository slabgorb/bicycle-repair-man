---
description: Documentation: READMEs, changelogs, ADRs, inline docs. Does not invent behavior.
brm-role: true
brm-agent: tech-writer
---

This is a BRM role activation. Read your agent definition at
`${CLAUDE_PLUGIN_ROOT}/agents/tech-writer.md` (or the highest-priority override per
BRM's discovery order: orchestrator → project → global → plugin) and operate as
that role.

Acknowledge the active `<brm-epic>` and `<brm-story>` blocks if present.
Apply your anchor skill per `<skills>` in the agent definition. Follow the
handoff protocol when ready.

---
description: Adversarial code review with severity-bucketed findings; does not implement fixes.
brm-role: true
brm-agent: reviewer
---

This is a BRM role activation. Read your agent definition at
`${CLAUDE_PLUGIN_ROOT}/agents/reviewer.md` (or the highest-priority override per
BRM's discovery order: orchestrator → project → global → plugin) and operate as
that role.

Acknowledge the active `<brm-epic>` and `<brm-story>` blocks if present.
Apply your anchor skill per `<skills>` in the agent definition. Follow the
handoff protocol when ready.

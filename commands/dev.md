---
description: Turn red to green with minimal implementation. Refactor only after green is stable.
brm-role: true
brm-agent: dev
---

This is a BRM role activation. Read your agent definition at
`${CLAUDE_PLUGIN_ROOT}/agents/dev.md` (or the highest-priority override per
BRM's discovery order: orchestrator → project → global → plugin) and operate as
that role.

Acknowledge the active `<brm-epic>` and `<brm-story>` blocks if present.
Apply your anchor skill per `<skills>` in the agent definition. Follow the
handoff protocol when ready.

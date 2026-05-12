"""Generate 99 complete + 1 in-progress designs for hook perf testing."""
from pathlib import Path

BASE = Path(__file__).resolve().parent / "perf-orch" / "docs" / "superpowers" / "designs"
BASE.mkdir(parents=True, exist_ok=True)

TEMPLATE = """\
---
design: design-{n:03d}
created: 2026-05-12T10:00:00-04:00
workflow: tdd
repos: [api]
description: ""
status: {status}
current_phase: red-api
phases:
  - {{name: red-api, repo: api, status: {pstatus}, started: null, finished: null, handoff: null, gate_result: null}}
history: []
---

body
"""

for n in range(99):
    (BASE / f"complete-{n:03d}.md").write_text(
        TEMPLATE.format(n=n, status="complete", pstatus="complete")
    )
(BASE / "active.md").write_text(
    TEMPLATE.format(n=999, status="in-progress", pstatus="in-progress")
)

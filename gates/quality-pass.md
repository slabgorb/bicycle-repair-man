<gate name="quality-pass" model="haiku">

<purpose>
Verify lint, typecheck, and tests all pass in ${repo.path}. Stricter than
tests-pass; used by optional verify phases.
</purpose>

<pass>
Run lint and typecheck (from repos.yaml's lint_command for ${phase.repo}),
plus the test_command.

GATE_RESULT:
  status: pass
  gate: quality-pass
  repo: ${phase.repo}
  message: "Lint, typecheck, and tests passing in ${phase.repo}"
  checks:
    - name: lint
      status: pass
      detail: "clean"
    - name: tests
      status: pass
      detail: "{N} passed"
</pass>

<fail>
Report which dimension failed:

GATE_RESULT:
  status: fail
  gate: quality-pass
  repo: ${phase.repo}
  message: "Quality gate blocked in ${phase.repo}"
  checks:
    - name: lint
      status: fail
      detail: "{N} lint errors"
  recovery:
    - "Fix lint errors in ${repo.path}"
    - "Re-run quality-pass after fix"
</fail>

</gate>

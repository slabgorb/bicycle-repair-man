<gate name="tests-fail" model="haiku">

<purpose>
Verify the red phase is complete in ${repo.path}: every acceptance criterion
listed in ${design.path} has at least one corresponding failing test, and the
phase's test files are syntactically valid.
</purpose>

<pass>
Inspect ${repo.path} for new or modified test files added in this phase. Cross-
reference against the design's `## Acceptance Criteria` checklist. Each AC must
have at least one test that fails when run.

If all ACs are covered by failing tests, return:

GATE_RESULT:
  status: pass
  gate: tests-fail
  repo: ${phase.repo}
  message: "All ACs covered by failing tests in ${phase.repo}"
  checks:
    - name: ac-coverage
      status: pass
      detail: "{N} ACs / {N} covered"
    - name: tests-fail
      status: pass
      detail: "{N} failing tests in ${repo.path}"
</pass>

<fail>
If any AC lacks a failing test, list the gaps:

GATE_RESULT:
  status: fail
  gate: tests-fail
  repo: ${phase.repo}
  message: "Red phase incomplete in ${phase.repo}"
  checks:
    - name: ac-coverage
      status: fail
      detail: "{N} ACs uncovered"
  recovery:
    - "Add failing tests covering: {list of uncovered ACs}"
    - "Run tests in ${repo.path} to confirm they fail"
</fail>

</gate>

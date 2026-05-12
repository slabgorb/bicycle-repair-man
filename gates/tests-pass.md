<gate name="tests-pass" model="haiku">

<purpose>
Verify the green phase is complete in ${repo.path}: tests pass, working tree
is clean of debug artifacts, no test files were deleted to make the suite
green.
</purpose>

<pass>
Run the repo's test command (from `.brm/repos.yaml`'s `test_command` field for
${phase.repo}). Verify the tree is clean (`git status --porcelain` returns no
unexpected entries). Verify no test files added in the previous red phase have
been deleted.

If all checks pass, return:

GATE_RESULT:
  status: pass
  gate: tests-pass
  repo: ${phase.repo}
  message: "Tests passing, tree clean in ${phase.repo}"
  checks:
    - name: tests
      status: pass
      detail: "{N} passed, 0 failed in ${repo.path}"
    - name: tree-clean
      status: pass
      detail: "no debug artifacts in working tree"
</pass>

<fail>
Report which check failed:

GATE_RESULT:
  status: fail
  gate: tests-pass
  repo: ${phase.repo}
  message: "Green phase blocked in ${phase.repo}"
  checks:
    - name: tests
      status: fail
      detail: "{N} failing tests in ${repo.path}"
  recovery:
    - "Fix failing tests in ${repo.path}"
    - "Remove debug artifacts before re-running gate"
</fail>

</gate>

<gate name="approval" model="haiku">

<purpose>
Verify a reviewer has signed off on the work in ${repo.path} (or across the
design if no repo is bound). Check the most recent reviewer handoff in the
design body for an APPROVED verdict.
</purpose>

<pass>
Find the most recent review-phase handoff in ${design.path}. Confirm its
summary states APPROVED.

GATE_RESULT:
  status: pass
  gate: approval
  repo: ${phase.repo}
  message: "Reviewer approved in ${phase.repo}"
  checks:
    - name: verdict
      status: pass
      detail: "APPROVED in handoff"
</pass>

<fail>
GATE_RESULT:
  status: fail
  gate: approval
  repo: ${phase.repo}
  message: "Reviewer not approved in ${phase.repo}"
  recovery:
    - "Re-run /reviewer in ${phase.repo} (or across the design for unscoped phases)"
    - "Address review findings before retrying"
</fail>

</gate>

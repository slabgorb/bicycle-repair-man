<gate name="design-complete" model="haiku">

<purpose>
Verify ${design.path} can be marked complete: every phase status is "complete"
with a passing gate result, and every acceptance criterion in the design body
is checked off.
</purpose>

<pass>
Read ${design.path}. Confirm all `phases[].status == "complete"`,
`phases[].gate_result in (pass, skip)`, and that every `- [ ]` checkbox in the
`## Acceptance Criteria` section is now `- [x]`.

GATE_RESULT:
  status: pass
  gate: design-complete
  message: "Design ${design.path} is complete"
  checks:
    - name: phases
      status: pass
      detail: "all phases complete with passing gates"
    - name: acceptance-criteria
      status: pass
      detail: "all ACs checked"
</pass>

<fail>
List remaining work:

GATE_RESULT:
  status: fail
  gate: design-complete
  message: "Design ${design.path} not complete"
  checks:
    - name: phases
      status: fail
      detail: "{N} phases not complete"
  recovery:
    - "Complete remaining phases: {list}"
    - "Check off remaining ACs: {list}"
</fail>

</gate>

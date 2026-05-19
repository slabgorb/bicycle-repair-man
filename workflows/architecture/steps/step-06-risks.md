# Step 6: Risks

<step-meta>
number: 6
name: risks
gate: true
next: step-07-document
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Identify the significant risks in the proposed design, assess their likelihood and impact, and define mitigations or explicit acceptance decisions for each.
</purpose>

<instructions>
1. List each risk: technical (scalability, correctness, security), organizational (ownership gaps, knowledge silos), and operational (deployment complexity, observability).
2. Score each risk: likelihood (low/medium/high) and impact (low/medium/high).
3. For high-severity risks (high likelihood or high impact), define a concrete mitigation.
4. For accepted risks, document the explicit acceptance rationale.
5. Identify any risks that would cause you to revisit the pattern selection from Step 3.
</instructions>

<output>
A risk register: risk description, likelihood, impact, severity, mitigation or acceptance rationale. Flag any risks that could trigger pattern reconsideration.
</output>

<gate>
## Completion criteria
- [ ] All high-likelihood or high-impact risks have a named mitigation
- [ ] Accepted risks have explicit rationale, not silent omissions
- [ ] Risks that could invalidate the pattern choice are called out
- [ ] Operational risks (deployment, observability) are included
</gate>

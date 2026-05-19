# Step 2: Context

<step-meta>
number: 2
name: context
gate: true
next: step-03-patterns
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Gather the constraints, quality attributes, and existing system context that will shape the design. Surface assumptions before they become hidden dependencies.
</purpose>

<instructions>
1. List hard constraints (regulatory, performance, budget, technology mandates).
2. List quality attributes in priority order (e.g., availability, consistency, latency).
3. Describe the relevant parts of the existing system — data flows, integration points, ownership boundaries.
4. Note open questions and assumptions that need to be validated.
5. Review the framing from Step 1 and refine if new context changes the scope.
</instructions>

<output>
A constraints and context document listing: hard constraints, ranked quality attributes, existing system summary, integration points, and open assumptions.
</output>

<gate>
## Completion criteria
- [ ] Hard constraints are listed and sourced
- [ ] Quality attributes are ranked, not just enumerated
- [ ] Existing integration points are identified
- [ ] Open assumptions are explicitly called out
</gate>

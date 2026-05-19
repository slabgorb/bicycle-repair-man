# Step 3: Patterns

<step-meta>
number: 3
name: patterns
gate: false
next: step-04-components
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Survey the architectural patterns applicable to this decision, evaluate each against the ranked constraints and quality attributes, and select the best candidate(s) to carry forward.
</purpose>

<instructions>
1. Enumerate 3–5 patterns or approaches relevant to the problem (e.g., event sourcing, CQRS, saga, strangler fig, pub/sub, layered, hexagonal).
2. For each pattern, note: what problem it solves, known trade-offs, and where it fits in the quality attribute ranking.
3. Cross-reference against the hard constraints from Step 2 to eliminate disqualified patterns.
4. Recommend 1–2 patterns to explore further, with justification.
5. Note any hybrid approaches worth considering.
</instructions>

<output>
A pattern survey table with columns: pattern name, trade-offs, constraint fit, and proceed/discard recommendation. Plus a short narrative justifying the selected candidate(s).
</output>

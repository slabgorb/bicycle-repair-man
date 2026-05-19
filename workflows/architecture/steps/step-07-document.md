# Step 7: Document

<step-meta>
number: 7
name: document
gate: false
next: null
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Write the Architecture Decision Record (ADR) that captures the decision, its context, the chosen design, and the rationale — in a form that will be useful to future maintainers.
</purpose>

<instructions>
1. Write the ADR using standard sections: Title, Status, Context, Decision, Consequences.
2. Context: summarize the problem framing (Step 1) and key constraints (Step 2) in 2–4 sentences.
3. Decision: describe the chosen design — components, patterns, and interfaces — concisely. Reference earlier steps by outcome, not by step number.
4. Consequences: list positive outcomes, trade-offs accepted, risks acknowledged, and any follow-on decisions deferred.
5. Include a "Supersedes / Related" section if this decision modifies or replaces an existing ADR.
6. Save as `docs/adr/NNNN-<short-title>.md` in the affected repository.
</instructions>

<output>
A completed ADR file with all standard sections populated, ready for review and merge.
</output>

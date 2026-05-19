# Step 5: Interfaces

<step-meta>
number: 5
name: interfaces
gate: false
next: step-06-risks
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Define the contracts between components: API shapes, message schemas, versioning strategy, and error semantics. Turn the component sketch into a testable boundary definition.
</purpose>

<instructions>
1. For each component boundary identified in Step 4, specify the interface type (REST, gRPC, event, queue, library call).
2. Draft the request/response or message schema for the primary operations (field names, types, required vs optional).
3. Define error codes or fault signals and their meaning for each interface.
4. State the versioning strategy (additive-only, semver, header-based).
5. Identify any shared schemas or contracts that must be agreed upon across team boundaries.
</instructions>

<output>
An interface catalog: one entry per boundary with interface type, schema sketch, error semantics, and versioning strategy.
</output>

# Step 4: Components

<step-meta>
number: 4
name: components
gate: true
next: step-05-interfaces
repo: $all
skill: superpowers:brainstorming
requires_skill: false
</step-meta>

<purpose>
Sketch the major components of the chosen design — their responsibilities, ownership, and relationships — before committing to interface details.
</purpose>

<instructions>
1. Name each logical component and describe its single responsibility.
2. Assign ownership: which team or service owns each component.
3. Draw the high-level component diagram (ASCII or describe relationships in prose).
4. Label the data flows between components (request/response, events, batch).
5. Flag any components that cross ownership or deployment boundaries.
</instructions>

<output>
A component map listing: component name, responsibility, owner, relationships, and data-flow labels. Include a diagram or structured description.
</output>

<gate>
## Completion criteria
- [ ] Each component has a single, named responsibility
- [ ] Ownership is assigned for every component
- [ ] Data flows are labelled with direction and payload type
- [ ] Cross-boundary components are flagged for extra scrutiny
</gate>

# Bicycle Repair Man (BRM) — v0.1.0 Design

**Date:** 2026-05-12
**Status:** Design approved; pending implementation plan.
**Predecessors:** [`/Users/slabgorb/Projects/orc-penny/pennyfarthing/`](https://github.com/slabgorb/pennyfarthing), [`superpowers` plugin v5.1.0](https://github.com/obra/superpowers), [`zeitgoose`](https://github.com/slabgorb/zeitgoose).

## Problem statement

Pennyfarthing (PF) is a Claude Code agent orchestration framework with a rich set of action-oriented patterns (role-bounded agents, gates, handoffs, sidecars, prime context) wrapped around sprint/Jira/story machinery that we want to leave behind. Superpowers ships a deep skill library (TDD, brainstorming, planning, debugging, review) but treats agents as anonymous executors of skills. Zeitgoose extracted PF's persona system as a clean Claude Code plugin.

BRM is the **role layer between superpowers and zeitgoose**: a Claude Code plugin that provides role-bounded slash commands with per-role persistent memory. It does *not* re-implement PF's CLI, server, sprint, or persona stack. It composes with the other two plugins via the standard Claude Code plugin surface (slash commands + hooks).

```
┌─────────────────────────────────────────────────────────┐
│  superpowers   (skills: TDD, brainstorming, planning…)  │  what to do
├─────────────────────────────────────────────────────────┤
│  brm           (roles + sidecars)                       │  who's doing it
├─────────────────────────────────────────────────────────┤
│  zeitgoose     (persona on bound commands)              │  what voice
└─────────────────────────────────────────────────────────┘
```

## Decisions

| Decision | Choice |
|---|---|
| Format | Pure Claude Code plugin (no CLI, no server, no daemon) |
| Activation | Slash command swaps role in the current conversation (no `Task`-subagent dispatch) |
| Roster (v1) | TEA, Dev, Reviewer, Architect, PM, Tech Writer |
| Excluded roles | SM, BA, Orchestrator (sprint-flavored or PF-meta — out of scope) |
| Sidecar scope | Project-first (`.brm/sidecars/`), global fallback (`~/.claude/brm/sidecars/`) |
| Sidecar write | Conversational — user says "add that to your sidecar," role uses `Write`/`Edit` |
| Sidecar read | `UserPromptSubmit` hook injects content on the activation turn (one-shot, not sticky) |
| Memory boundary | While a role is active, role-specific lessons go to the sidecar; user/project/reference auto-memory continues normally |
| Command names | Bare (`/reviewer`) and auto-namespaced (`/brm:reviewer`) — no hyphenated `brm-` filename prefix |

## Section 1 — Architecture & composition

### Wire diagram (one turn, `/reviewer look at the cache change`)

```
Claude Code receives prompt
   │
   ├─ UserPromptSubmit hooks fire (independently):
   │   ├─ brm: detects /reviewer; reads
   │   │       .brm/sidecars/reviewer.md (project) +
   │   │       ~/.claude/brm/sidecars/reviewer.md (global);
   │   │       emits <brm-sidecar role="reviewer">…</brm-sidecar>
   │   └─ zeitgoose: detects /reviewer; looks up binding;
   │                 emits <zeitgoose-persona>…</zeitgoose-persona>
   │
   ├─ Slash command resolves: commands/reviewer.md is the role brief
   │
   └─ Claude sees:
       user message + brm-sidecar + zeitgoose-persona + role brief
       → responds in role, with memory, with voice
       → may invoke superpowers skills (requesting-code-review etc.)
```

### Properties

- **No shared state between plugins.** Each fires an independent `UserPromptSubmit` hook. Composition happens in Claude's combined context, not via plugin-to-plugin APIs.
- **One-shot injection.** BRM's hook injects only when the leading token is a role command. Bare turns inject nothing. Refresh = re-fire the command.
- **Same-conversation activation.** The current Claude *becomes* the role. No subagent spawning.
- **Memory boundary signaled, not enforced.** The role brief tells Claude where role-specific lessons go; auto-memory continues for role-agnostic facts.

## Section 2 — Sidecar contract

### Filesystem

```
<project>/.brm/sidecars/                # project-scoped, tracked or .gitignored per user
├── tea.md
├── dev.md
├── reviewer.md
├── architect.md
├── pm.md
└── tech-writer.md

~/.claude/brm/sidecars/                 # global, follows user across projects
├── tea.md
├── dev.md
└── …                                   # only roles that have accumulated global lessons
```

One file per role. Project files do not override; both layers contribute, concatenated by the hook.

### File format

Three H2 sections, fixed: `## Patterns`, `## Gotchas`, `## Decisions`. Entries are bullets, newest at top, ISO-dated.

```markdown
# Reviewer sidecar

## Patterns
- 2026-02-14 — Tests-first reviews catch ~3x more issues than tests-after. Always
  scan the test file before the implementation.

## Gotchas
- 2026-01-09 — Async fixtures in pytest-asyncio v0.23 silently swallow errors if
  `asyncio_mode = "strict"` isn't set. (see `tests/conftest.py`)

## Decisions
- 2026-02-20 — Project policy: don't flag missing type hints unless the function
  is exported.
```

Roles may add additional H2 sections at their own risk; the hook injects them verbatim, no enforcement.

### Path resolution (`lib/sidecar.py`)

```python
def load_sidecar(role: str) -> str:
    """Returns concatenated sidecar content for `role`, or '' if neither layer present."""
```

- Reads `~/.claude/brm/sidecars/{role}.md` if present.
- Reads `<project_root>/.brm/sidecars/{role}.md` if present. `project_root` = nearest ancestor of `cwd` containing `.git` or `.brm/`; walk capped at 20 levels.
- Concatenates global first, then project; each layer wrapped with a source marker:

  ```
  <brm-sidecar role="reviewer">
    <layer scope="global" path="~/.claude/brm/sidecars/reviewer.md">
  …verbatim contents…
    </layer>
    <layer scope="project" path=".brm/sidecars/reviewer.md">
  …verbatim contents…
    </layer>
  </brm-sidecar>
  ```

- Only present layers appear. No empty wrappers.
- Returns `""` if neither layer present; hook then emits nothing.

### Write semantics

Conversational. Two flows:

1. **User-directed:** "Add that finding to your sidecar." The active role appends a bullet under the appropriate H2 section in `.brm/sidecars/{role}.md` using `Edit`/`Write`, with today's ISO date as a leading prefix. The role brief specifies path, section names, bullet format.

2. **Memory boundary directive (from the role brief):** While a role is active, role-specific patterns/gotchas/decisions go to the sidecar; user profile, project facts, and references continue to flow to auto-memory as normal. This is signal to Claude, not enforcement.

### Deliberately not in v1

- Size capping / trimming. Easy knob to add later in `load_sidecar`.
- Cross-role / shared / "team" sidecars.
- Sidecar management commands (`/brm:sidecar show|where|edit`).
- Schema validation of sidecar content.

## Section 3 — Hook behavior

### Trigger detection

The `UserPromptSubmit` hook inspects only the first whitespace-separated token of the user's prompt. Matches (case-sensitive):

```
/tea            /brm:tea
/dev            /brm:dev
/reviewer       /brm:reviewer
/architect      /brm:architect
/pm             /brm:pm
/tech-writer    /brm:tech-writer
```

No match → exit 0 silently. Non-match must do **zero filesystem I/O** — this is the common case and must be cheap.

### Decision flow

```
leading token == /role or /brm:role ?
   │
no ┴ yes
│      │
│      ▼
│   role = extract(token)
│   global_path  = ~/.claude/brm/sidecars/<role>.md
│   project_root = nearest ancestor with .git or .brm/
│   project_path = <project_root>/.brm/sidecars/<role>.md
│      │
│      ▼
│   both files missing? ── yes ──→ exit 0 silently
│      │ no
│      ▼
│   emit <brm-sidecar role="…"> with present layers only; exit 0
▼
exit 0 silently
```

### Failure modes

| Failure | Behavior |
|---|---|
| Sidecar file unreadable | Skip that layer; emit the other if present; log to stderr |
| Both files unreadable | Behave as if both missing — exit silent |
| Project-root walk hits filesystem root with no `.git`/`.brm` | Skip project layer; emit global if present |
| Hook itself raises | Top-level try/except logs to stderr and exits 0. Missing sidecar is far better than a blocked prompt. |
| Pathologically large sidecar (>1 MB) | Emit as-is in v1; trimming deferred |

### Stateless

The hook holds no state between turns. No "currently active role" file. One-shot injection means there's nothing to remember.

### Interaction with Zeitgoose

Independent hook, same event. Order doesn't matter (each plugin emits its own block; Claude reads both). No shared state, no negotiation.

## Section 4 — Role briefs (`commands/*.md`)

### Common structure

Every brief follows this template (~600-900 tokens per file):

```markdown
---
description: <one-line, shows in /help>
---

# {Role} — {one-line elevator pitch}

## Who you are
<2-4 sentences: identity + scope + posture>

## What you do
<bulleted, narrow>

## What you don't do
<bulleted: work belonging to other roles or to the user>

## Skills you invoke
<which superpowers skills are this role's primary tools>

## Sidecar protocol
- Read on activation: handled by the hook (no action needed).
- Write on request: when the user says "add that to your sidecar"
  (or similar), append to `.brm/sidecars/{role}.md` under the
  appropriate H2 section, with today's ISO date as a leading prefix.
- Sections are `## Patterns` / `## Gotchas` / `## Decisions`.
- Newest entries at the top.

## Memory boundary
While in this role, role-specific lessons go to the sidecar. User
profile, project facts, and references continue to flow to auto-memory.

## Handing off
When work this role can do is complete, name the next role plainly
(e.g., "this needs /dev next"). The user decides whether to fire it.
Do not invoke other roles via Task — same-conversation handoff only.
```

### Distinctive content per role

| Role | Distinctive content |
|---|---|
| **TEA** | Skills: `superpowers:test-driven-development`. Emphasizes writing the *failing* test first, watching it fail. Handoff to `/dev` once RED with a clear error. |
| **Dev** | Skills: `test-driven-development`, `systematic-debugging`. Emphasizes minimal code to turn red → green. "Don't refactor while green is fragile." Handoff to `/reviewer` once tests pass. |
| **Reviewer** | Skills: `requesting-code-review`, `verification-before-completion`. Adversarial posture — finds issues by severity (Critical/Major/Minor/Nit), proposes fixes, does not implement. Handoff to `/dev` or `/tea` per finding. |
| **Architect** | Skills: `brainstorming`, `writing-plans`. Design exploration and spec-check. Produces plans/designs, not implementation. Handoff to `/tea` once a plan is approved. |
| **PM** | Skills: `brainstorming`, `writing-plans`. Thin brief — mostly a voice/frame around superpowers' skills. Honest about that in "Who you are." |
| **Tech Writer** | No superpowers skill binding (no doc-skill in superpowers' v5.1.0). Covers READMEs, changelogs, ADRs, inline docs. "Don't invent behavior; if docs and code disagree, flag and stop." |

### Token budget

Each brief lands at 600-900 tokens. Total role-brief surface ~4-5K tokens, but only one loads per activation.

### Deliberately not in briefs

- Persona content (that's Zeitgoose's job)
- Project-specific knowledge (lives in sidecars or project `CLAUDE.md`)
- Tool restrictions (honor-system via "What you don't do"; real tool gates would require Task-subagent activation, ruled out)

## Section 5 — Plugin shape, install, error handling, testing

### File tree (v1)

```
bicycle-repair-man/
├── .claude-plugin/
│   └── plugin.json
├── hooks/
│   ├── hooks.json
│   └── on-user-prompt-submit.py
├── commands/
│   ├── tea.md
│   ├── dev.md
│   ├── reviewer.md
│   ├── architect.md
│   ├── pm.md
│   └── tech-writer.md
├── lib/
│   └── sidecar.py
├── docs/
│   ├── sidecar-schema.md
│   └── superpowers/specs/2026-05-12-brm-design.md (this file)
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_sidecar_paths.py
│   ├── test_hook_match.py
│   ├── test_hook_output.py
│   ├── test_hook_perf.py
│   └── test_commands_parse.py
├── pyproject.toml
├── CLAUDE.md
├── README.md
└── assets/hero.png
```

### Plugin manifest (`.claude-plugin/plugin.json`)

```json
{
  "name": "brm",
  "description": "Role-bounded slash commands (TEA, Dev, Reviewer, Architect, PM, Tech Writer) with per-role persistent sidecar memory. Companion to superpowers and zeitgoose.",
  "version": "0.1.0",
  "author": { "name": "Keith Avery", "email": "slabgorbai@gmail.com" },
  "license": "Apache-2.0",
  "keywords": ["roles", "agents", "memory", "superpowers", "pennyfarthing"]
}
```

### Hook registration (`hooks/hooks.json`)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/on-user-prompt-submit.py\"",
            "async": false
          }
        ]
      }
    ]
  }
}
```

### Install

1. **Symlink (dogfooding):** `ln -s /Users/slabgorb/Projects/brm ~/.claude/plugins/brm`
2. **Git clone:** `git clone https://github.com/slabgorb/bicycle-repair-man ~/.claude/plugins/brm`
3. **Marketplace** — deferred past v1.

Restart Claude Code after install.

### Error handling (plugin-level)

| Failure | Effect | Mitigation |
|---|---|---|
| Hook raises | stderr surfaces in Claude Code's hook log; prompt still goes through without sidecar injection | Top-level try/except in hook body; exit 0 on any failure |
| Sidecar file unreadable | One layer drops; the other (if present) still injects | Per-layer try/except in `load_sidecar`; `errors="replace"` on read |
| Plugin manifest malformed | Claude Code refuses to load plugin; no role commands appear | CI validates `plugin.json` against Claude Code's plugin schema |
| Role brief malformed | Slash command still runs; brief is whatever's in the file | `test_commands_parse.py` lints every brief in CI |

### Testing

Five pytest files, stdlib-only, CI on Python 3.11 + 3.12:

1. **`test_sidecar_paths.py`** — unit on `load_sidecar`. Cases: both present / global-only / project-only / neither / no project root / permission denied on one layer.
2. **`test_hook_match.py`** — leading-token matcher. Cases: `/reviewer foo`, `/brm:reviewer foo`, `/reviewer-fresh` (no match — longer prefix), leading whitespace, non-leading (`please /reviewer`), case (`/Reviewer` no match), empty.
3. **`test_hook_output.py`** — golden-output comparison per scenario (match + both layers, match + global only, match + project only, no match).
4. **`test_hook_perf.py`** — non-match path must do zero filesystem reads. `monkeypatch` `Path.read_text` and assert it's never called on non-matching input.
5. **`test_commands_parse.py`** — for each `commands/*.md`: frontmatter `description` present; required H2 sections present in order; word count within budget (~675 words ≈ 900 tokens); no `TODO`/`TBD`.

### Documentation deliverables

- `README.md` — install, one example turn, the 3-plugin composition diagram.
- `docs/sidecar-schema.md` — file format reference cross-linked from each role brief.
- `CLAUDE.md` — updated from "in design" to "v0.1.0 spec committed; implementation pending."

## Out of scope for v1 (deferred backlog)

- Marketplace registration.
- Sidecar trimming / cap-by-section / N-most-recent.
- Sidecar management commands (`/brm:sidecar show|where|edit`).
- Context-isolated subagent helper (`agents/reviewer-fresh.md`).
- Cross-role / team sidecars.
- Schema enforcement of sidecar content beyond passthrough.
- Workflow definitions / YAML choreography (will live in a separate plugin per user decision).
- Doc-writing skill for Tech Writer (no superpowers analogue exists yet).

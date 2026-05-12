# Bicycle Repair Man (BRM)

> Role-bounded slash commands for Claude Code, with per-role persistent
> sidecar memory.

![BRM hero](assets/hero.png)

BRM is the **role layer** that sits between [superpowers][] (skills) and
[zeitgoose][] (personas). It gives you six bound slash commands —
`/tea`, `/dev`, `/reviewer`, `/architect`, `/pm`, `/tech-writer` — each with
its own persistent memory, scoped per project and globally.

```
┌─────────────────────────────────────────────────────────┐
│  superpowers   (skills: TDD, brainstorming, planning…)  │  what to do
├─────────────────────────────────────────────────────────┤
│  brm           (roles + sidecars)                       │  who's doing it
├─────────────────────────────────────────────────────────┤
│  zeitgoose     (persona on bound commands)              │  what voice
└─────────────────────────────────────────────────────────┘
```

## Install

```bash
git clone https://github.com/slabgorb/bicycle-repair-man ~/.claude/plugins/brm
```

Or symlink your working copy:

```bash
ln -s "$(pwd)" ~/.claude/plugins/brm
```

Restart Claude Code. The six role commands appear in `/help`.

## How it works

When your prompt begins with a recognized role token (`/reviewer foo` or
`/brm:reviewer foo`), BRM's `UserPromptSubmit` hook reads two files:

- `~/.claude/brm/sidecars/reviewer.md` — global lessons
- `<project_root>/.brm/sidecars/reviewer.md` — project lessons

…and injects whatever is present as `<brm-sidecar>` context, then the role
brief at `commands/reviewer.md` loads. The current Claude becomes the
Reviewer for that turn (and as long as the conversation stays on that
thread).

Non-role prompts incur zero filesystem I/O.

See [`docs/sidecar-schema.md`](docs/sidecar-schema.md) for the sidecar
file format.

## Writing to sidecars

Just tell the active role: "add that to your sidecar." The role appends an
ISO-dated bullet to the appropriate section in
`.brm/sidecars/<role>.md`.

## What BRM does not do

- No CLI. No server. No daemon.
- No sprint/story/Jira machinery — that belongs to Pennyfarthing or its
  successor.
- No personas — that's [zeitgoose][]'s job.
- No subagent dispatch. The current Claude *becomes* the role.

[superpowers]: https://github.com/obra/superpowers
[zeitgoose]: https://github.com/slabgorb/zeitgoose

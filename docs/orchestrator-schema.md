# BRM orchestrator schema

This document specifies `.brm/repos.yaml` — the BRM-owned config that marks a
directory as an orchestrator workspace and declares the subrepos that live
inside it.

## Location

```
<orchestrator_root>/.brm/repos.yaml
```

The presence of this file is the *only* signal BRM uses to identify an
orchestrator workspace. Resolution: BRM walks up from the current directory
looking for the nearest ancestor whose `.brm/repos.yaml` is a regular file,
with a 20-level walk cap.

## Schema

```yaml
repos:
  <short-name>:                    # alphanumeric + hyphen + underscore
    path: <relative path>          # REQUIRED; relative to the directory containing .brm/
    type: <free string>            # REQUIRED; convention: api / ui / framework / orchestrator / lib / …
    default_branch: <branch>       # REQUIRED; e.g. main, develop
    test_command: <shell string>   # REQUIRED; empty string allowed if no test runner
    lint_command: <shell string>   # REQUIRED; empty string allowed
    description: <one-liner>       # OPTIONAL; defaults to ""
    build_command: <shell string>  # OPTIONAL; defaults to ""
```

### Rules

- Top-level: must be a mapping with a `repos:` key whose value is a non-empty
  mapping. Other top-level keys are reserved for future versions and produce a
  warning to stderr; they are ignored, not rejected.
- Per-repo: all required keys must be present. Unknown keys produce a stderr
  warning and are ignored.
- `path: .` is valid and means the orchestrator root itself is a repo.
- The schema is closed — additional fields will be added in v0.3+ and
  documented in the changelog.

### Example

```yaml
repos:
  orchestrator:
    path: .
    type: orchestrator
    description: Sprint management and framework development coordination
    default_branch: main
    test_command: ""
    lint_command: ""
    build_command: ""
  api:
    path: api
    type: api
    description: REST API server
    default_branch: main
    test_command: pytest
    lint_command: ruff check
    build_command: ""
  ui:
    path: ui
    type: ui
    description: React client
    default_branch: main
    test_command: npm test
    lint_command: npm run lint
    build_command: npm run build
```

## Injection format

When a role command (`/<role>` or `/brm:<role>`) is the leading token of a
user prompt and an orchestrator root is detected, the hook emits:

```
<brm-orchestrator root="<absolute path>" cwd-repo="<short-name>">
<repos.yaml>
<verbatim contents of repos.yaml>
</repos.yaml>
</brm-orchestrator>
```

The `cwd-repo` attribute is omitted when the cwd is not under any declared
repo's `path`. The body is the raw `repos.yaml` text — no translation, no
field reordering, no comment stripping.

## Failure handling

| Condition | Hook behavior | Script behavior |
|---|---|---|
| File missing | Treat as non-orchestrator workspace | Most subcommands exit 1 with "not in an orchestrator workspace"; `init` is the exception |
| Malformed YAML | Drop `<brm-orchestrator>` block; sidecars still emit; log to stderr; exit 0 | Exit 1 with parse error |
| Missing required field | Drop block; log to stderr; exit 0 | Exit 1 with schema error |
| Repo declared but its `path` doesn't exist on disk | Block still emits (verbatim file content) | `list` still names the repo; `topology --json` shows it; `status`/`snapshot`/`branch` skip with a stderr warning |

## Initializing a new workspace

```bash
$CLAUDE_PLUGIN_ROOT/scripts/brm-repos init
```

Writes a starter `repos.yaml` to `<cwd>/.brm/repos.yaml`. Use `--from-pf` to
import an existing `.pennyfarthing/repos.yaml` (PF-only fields are dropped
with a stderr summary). Use `--force` to overwrite an existing file.

## Deliberately not in v0.2

- Schema validation as a standalone command (`brm-repos validate`).
- Auto-discovery of subrepos without a declared entry.
- Cross-repo workflow / gate definitions (deferred to v0.3).
- Per-repo agent overrides.
- Worktree fan-out (`brm-repos worktree create/remove/list`).

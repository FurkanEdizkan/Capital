---
name: conventional-commits
description: >-
  Write a git commit message that follows the Conventional Commits 1.0.0 spec as
  enforced by this repo (commitlint @config-conventional + husky commit-msg hook
  + CI). Use whenever you are about to create a commit, are asked to commit
  staged changes, need help choosing a type/scope, or want to fix a commit
  message that commitlint rejected.
---

# Conventional Commits

This repo enforces [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
on every commit via:

- `commitlint.config.js` → `@commitlint/config-conventional`
- the husky `commit-msg` hook (`.husky/commit-msg` runs `commitlint --edit`)
- a commitlint check in CI

A commit that doesn't match the format is **rejected before it lands**, so
getting the type and format right matters.

## The format

```text
<type>(<optional scope>): <description>

<optional body>

<optional footer(s)>
```

Rules commitlint enforces (config-conventional defaults):

- **type** is required, lowercase, and from the allowed list below.
- **scope** is optional; when present it's in parentheses, lowercase.
- **description** is required: a `: ` then a short summary, lowercase start, no
  trailing period, imperative mood ("add", not "added"/"adds").
- **header** (the first line) must be ≤ 100 characters.
- **body and footer** lines must each be ≤ 100 characters
  (`body-max-line-length` / `footer-max-line-length`) — hard-wrap long
  paragraphs; a single long line **will** fail commitlint/CI.
- a **blank line** must separate header from body, and body from footer.

## Allowed types

| Type       | Use for                                                  |
| ---------- | -------------------------------------------------------- |
| `feat`     | a new feature                                            |
| `fix`      | a bug fix                                                |
| `docs`     | documentation only                                       |
| `refactor` | code change that neither fixes a bug nor adds a feature  |
| `test`     | adding or correcting tests                               |
| `chore`    | build, deps, tooling, housekeeping                       |
| `ci`       | CI configuration / pipeline changes                      |
| `perf`     | a performance improvement                                |
| `build`    | build system or external dependency changes              |
| `style`    | formatting/whitespace, no code-meaning change            |
| `revert`   | reverting a previous commit                              |

CONTRIBUTING.md highlights `feat`, `fix`, `chore`, `docs`, `refactor`, `test`,
`ci` as the everyday set — prefer those unless another clearly fits better.

## Scopes used in this repo

The codebase is split into two apps, so the scope is usually one of:

- `engine` — Python trading engine + API (`engine/`)
- `web` — React + Vite + TypeScript dashboard (`web/`)

Other reasonable scopes: a subsystem name (`api`, `db`, `deploy`, `ci`, `docker`).
Scope is optional — omit it for repo-wide changes (e.g. `chore: bump deps`).

## Breaking changes

Signal a breaking change in **either** way (or both):

- a `!` after the type/scope: `feat(engine)!: drop legacy order schema`
- a footer: `BREAKING CHANGE: <what broke and the migration path>`

## Referencing issues

Per CONTRIBUTING.md, reference the issue in the summary or body, e.g. `(#12)`.
Put `Closes #<issue>` in the **PR** description (not the commit) to auto-close.

## Examples

```text
feat(engine): add binance client wrapper

fix(web): prevent dashboard crash when a venue is offline (#118)

docs: document the conventional-commits workflow

refactor(engine): extract order routing into its own module

chore: bump commitlint to v19.6

feat(engine)!: switch order ids to uuidv7

BREAKING CHANGE: existing integer order ids are no longer accepted by the
API; run the 0003_uuid_orders migration before deploying.
```

## How to commit (workflow)

When asked to commit, don't just guess a message — derive it from the diff:

1. **Look at what changed.** Run `git status` and `git diff --staged` (and
   `git diff` for unstaged). If nothing is staged, decide with the user what to
   stage, or stage the relevant files.
2. **Pick the type** from the table above based on the *intent* of the change,
   not the file kind (editing a `.py` test file is still `test:`).
3. **Pick a scope** — `engine`, `web`, or a subsystem — or omit it for
   repo-wide changes.
4. **Write the header** in imperative mood, ≤ 100 chars, lowercase after the
   colon, no trailing period.
5. **Add a body** (after a blank line) when the change needs the "why" or has
   notable details. Wrap at ~72 chars. Reference the issue, e.g. `(#12)`.
6. **Add footers** for breaking changes (`BREAKING CHANGE:`) or co-authors.
7. **Commit.** Use a multi-line message so the body survives:

   ```bash
   git commit -m "feat(engine): add binance client wrapper" \
              -m "Wraps the REST + websocket clients behind one interface. (#12)"
   ```

   The husky `commit-msg` hook runs commitlint automatically. If the commit is
   **rejected**, read commitlint's output, fix the offending part (usually a
   missing/invalid type, a capitalized or period-terminated subject, or a
   header over 100 chars), and recommit.

## Quick checklist before committing

- [ ] starts with an allowed lowercase `type`
- [ ] scope (if any) is in `()` and lowercase
- [ ] `: ` then an imperative, lowercase summary with no trailing period
- [ ] header ≤ 100 characters
- [ ] breaking change marked with `!` and/or a `BREAKING CHANGE:` footer
- [ ] body separated by a blank line; issue referenced if relevant

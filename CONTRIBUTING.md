# Contributing to Capital

Capital is a self-hosted automated Binance trading platform. This guide covers
how to set up, branch, commit and open PRs.

## Project layout

```text
engine/   Python trading engine + API (uv, FastAPI, PostgreSQL)
web/      React + Vite + TypeScript dashboard
```

## Local setup

To run the whole stack in Docker with one command, use the installer:

```bash
scripts/install.sh
```

To develop a single service directly (hot reload, native tooling):

```bash
# 1. PostgreSQL
docker compose up -d postgres

# 2. Engine
cd engine
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload     # http://localhost:8000

# 3. Web
cd web
npm install
npm run dev                          # http://localhost:5173
```

## Skills (Claude Code)

Shared dev-practice skills (Conventional Commits, Conventional Branches, modular
service units) come from the central
[My-Skills](https://github.com/FurkanEdizkan/My-Skills) plugin marketplace,
registered in `.claude/settings.json` (`furkanedizkan-skills` → the `skills`
plugin). They are no longer vendored under `.claude/skills/`.

Registering the marketplace in settings does not auto-install it, so once per
machine activate the plugin from inside this repo in Claude Code:

```text
/plugin install skills@furkanedizkan-skills
```

If Claude Code doesn't already know the marketplace, add it first with
`/plugin marketplace add FurkanEdizkan/My-Skills`. The skills then activate by
description, or invoke one explicitly as `/skills:<name>` (e.g.
`/skills:conventional-commits`).

## Branching

`main` is protected — no direct pushes. All changes land via Pull Request.

Branch off `main` with a typed, issue-numbered name:

```text
<type>/<issue#>-<short-slug>     e.g. feat/12-binance-client
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`.

## Commits — Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org):

```text
<type>(<scope>): <summary>        e.g. feat(engine): add binance client wrapper
```

Reference the issue in the body or summary (`(#12)`). Commit linting runs in CI.

## Before opening a PR

Run the same checks CI runs:

```bash
# engine
cd engine && uv run ruff check . && uv run pytest

# web
cd web && npm run lint && npm run build
```

- Include an Alembic migration for any DB schema change.
- After changing an engine API endpoint or model, regenerate the API schema
  so CI's drift check passes:

  ```bash
  cd engine && uv run python export_openapi.py   # updates web/openapi.json
  cd web && npm run gen:api                       # updates src/lib/api/schema.d.ts
  ```

- Open the PR against `main`, fill in the template, and add `Closes #<issue>`.
- CI must pass; a review is required (the repo admin may self-merge solo work).

## Merging

PRs are merged with a **merge commit** — *not* squashed — so each feature's
branch and its individual commits stay visible in the history graph
(`git log --graph`). The merged branch is then deleted; the merge commit
already preserves the branching topology, so the graph is unaffected.

## Workflow

Work is tracked on the **Capital** GitHub Project board. Pick an issue from
`Todo`, move it to `In Progress`, and let merging the PR close it.

# Contributing to Capital

Thanks for your interest in Capital! This document explains how to set up your
environment, the branching model, and the rules we ask contributors to follow.

## Code of conduct

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
Be kind. Assume good faith.

## Project layout

```text
engine/   Python trading engine + API (uv, FastAPI, PostgreSQL)
web/      React + Vite + TypeScript dashboard
docs/     architecture, branching, PR guidelines, releases, venue setup
```

## Getting started

```sh
git clone https://github.com/FurkanEdizkan/Capital.git
cd Capital
git checkout test          # always branch off test, never main
git switch -c feat/my-thing
```

The fastest path to a running stack is the installer (Docker + Compose v2):

```sh
scripts/install.sh                # development mode — hot reload
scripts/install.sh prod           # production-style mode — built assets
```

To develop a single service directly (hot reload, native tooling):

```sh
# 1. PostgreSQL
docker compose up -d postgres

# 2. Engine
cd engine
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload     # http://localhost:8000

# 3. Web (in another shell)
cd web
npm install
npm run dev                          # http://localhost:5173
```

## Branching model

Capital uses a **two-trunk** model.

```text
contributors  ->  feature/*  ->  PR into test  ->  CI green  ->  merged into test
                                                                       |
                                                          automated PR test -> main
                                                                       |
                                                                  CI green
                                                                       v
                                                                main (stable)
```

- **`main`** is the stable branch. Releases are tagged from `main`. **Never**
  open a PR directly into `main`.
- **`test`** is the integration branch. All contributor PRs target `test`.
- A GitHub workflow opens (or refreshes) a PR from `test` into `main` whenever
  CI on `test` is green. Maintainers review and merge that PR to ship.

See [docs/branching.md](docs/branching.md) for the full model and the
branch-protection settings maintainers must configure.

## Pull request workflow

1. Create a topic branch off `test`. Use prefixes: `feat/`, `fix/`, `docs/`,
   `refactor/`, `chore/`, `ci/`, `test/`, `perf/`.
2. Make your changes. Add or update tests.
3. Ensure the project's lint + test commands pass locally:
   - Engine: `cd engine && uv run ruff check . && uv run pytest`
   - Web: `cd web && npm run lint && npm run build`
   - If you changed an engine API endpoint or model, regenerate the schema:
     `cd engine && uv run python export_openapi.py`
     `cd web && npm run gen:api`
4. Push and open a PR **into `test`**. Fill out the PR template.
5. Address review feedback. CI must be green before merge.
6. Maintainers merge with a merge commit (not squash). Your PR title becomes the
   merge commit message, so it must follow Conventional Commits — and because
   every commit on your branch is preserved in history, write those cleanly and
   Conventionally too.

Read [docs/pull-requests.md](docs/pull-requests.md) for the full checklist.

## Commit messages

We follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

Format:

```text
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

Allowed `type`s: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`.

The scope is optional and free-form — use the area of the codebase you touched
(`engine`, `web`, `api`, `ui`, `infra`, `ci`, `docs`, …).

Examples:

- `feat(engine): add binance client wrapper`
- `fix(web): crash on empty positions list`
- `docs: clarify local setup steps`

Breaking changes use `!` and a `BREAKING CHANGE:` footer:

```text
feat(api)!: rename `path` field to `source`

BREAKING CHANGE: clients must update the field name.
```

PR titles are validated against `.commitlintrc.yaml` by the **Commitlint**
workflow; the local husky `commit-msg` hook applies the same rules.

## Testing

- Keep tests close to the code they cover.
- Prefer small, real fixtures over heavy mocks when verifying behavior.
- Add a regression test with every bug fix.
- Engine tests run against a real PostgreSQL (CI brings one up). Don't mock
  the database.

## Reporting bugs / requesting features

Use the GitHub issue templates. Include your OS, the project version or commit,
and clear reproduction steps.

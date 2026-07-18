# AGENTS.md

Guidance for AI coding assistants (Claude Code, Cursor, Copilot, etc.) working
in **Capital**. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## The one rule that matters most

**Branch off `test`, open PRs into `test`. Never push to or PR into `main`.**
`main` is promoted from `test` automatically once CI is green. See
[docs/branching.md](docs/branching.md).

## Conventions

- **Commits & PR titles**: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
  The PR title becomes the merge commit, and the Commitlint workflow rejects
  non-conforming titles.
- **One logical change per PR.** Don't bundle unrelated refactors.
- **Tests travel with code.** Every behavior change needs a test; every bug fix
  needs a regression test.
- **Keep CI honest.** Run the project's lint + test commands before proposing a
  change; they should match `.github/workflows/ci.yml`:
  - Engine: `cd engine && uv run ruff check . && uv run pytest`
  - Web: `cd web && npm run lint && npm run build`
- **OpenAPI sync.** When you change an engine API endpoint or model, regenerate
  the schema so CI's drift check passes:
  `cd engine && uv run python export_openapi.py && cd ../web && npm run gen:api`.

## Where things live

- `engine/` — Python 3.12 + FastAPI trading engine (market data, strategies,
  executors, accounting, REST + WebSocket API, MCP server).
- `web/` — React 19 + Vite + TypeScript dashboard.
- `docs/` — architecture, branching, PR guidelines, releases, venue setup, deployment.
- `caddy/` — reverse-proxy config for production.
- `scripts/` — `install.sh`, `deploy.sh`, backup/restore helpers.
- CI / automation: [`.github/workflows/`](.github/workflows/).

## Skills

Capital ships two kinds of Claude skills:

- **Vendored, always present** — committed under
  [`.claude/skills/`](.claude/skills/) so every contributor and agent has them
  on clone with no setup: `conventional-commits` and `conventional-branches`
  (use these when writing commits/branches), plus `design-taste-frontend`.
  Versions are pinned in
  [`.claude/skills/skills-lock.json`](.claude/skills/skills-lock.json); run
  `npm run skills:check` to see upstream updates and `npm run skills:update` to
  pull them (opt-in — never runs in a git hook). See
  [`.claude/skills/README.md`](.claude/skills/README.md).
- **Marketplace plugin** — the
  [`FurkanEdizkan/My-Skills`](https://github.com/FurkanEdizkan/My-Skills)
  marketplace + `skills` plugin are pre-registered in
  [`.claude/settings.json`](.claude/settings.json) and provide the rest
  (`modular-services`, `three-tier-git-flow`, `create-github-issue`). Claude
  Code offers to install it on first open; to do it manually:

  ```sh
  /plugin marketplace add FurkanEdizkan/My-Skills
  /plugin install skills@furkanedizkan-skills
  ```

## Before you say "done"

- [ ] Lint + tests pass locally for the area you touched.
- [ ] New/changed behavior is covered by tests.
- [ ] OpenAPI / generated types regenerated if you touched the engine API.
- [ ] Docs updated if user-facing behavior changed.
- [ ] PR targets `test`; title is a valid Conventional Commit.

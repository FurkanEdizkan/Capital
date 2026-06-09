# AGENTS.md

Guidance for AI coding assistants (Claude Code, Cursor, Copilot, etc.) working
in **Capital**. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## The one rule that matters most

**Branch off `test`, open PRs into `test`. Never push to or PR into `main`.**
`main` is promoted from `test` automatically once CI is green. See
[docs/BRANCHING.md](docs/BRANCHING.md).

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

This repo's Claude skills live in the
[`FurkanEdizkan/My-Skills`](https://github.com/FurkanEdizkan/My-Skills) plugin
marketplace, not in `.claude/skills/`. The marketplace and the `skills` plugin
are pre-registered in [`.claude/settings.json`](.claude/settings.json), so
Claude Code will offer to trust + install them automatically the first time you
open this repo. If you need to install manually:

```sh
/plugin marketplace add FurkanEdizkan/My-Skills
/plugin install skills@furkanedizkan-skills
```

Provided: `conventional-commits`, `conventional-branches`, `modular-services`.

## Before you say "done"

- [ ] Lint + tests pass locally for the area you touched.
- [ ] New/changed behavior is covered by tests.
- [ ] OpenAPI / generated types regenerated if you touched the engine API.
- [ ] Docs updated if user-facing behavior changed.
- [ ] PR targets `test`; title is a valid Conventional Commit.

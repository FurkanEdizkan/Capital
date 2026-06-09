# Pull Request Guidelines

This is the checklist a PR must satisfy to get merged into `test`. Maintainers
use it during review.

## Targeting

- [ ] PR is opened against **`test`**, not `main`.
- [ ] The branch name has a meaningful prefix: `feat/`, `fix/`, `docs/`,
      `refactor/`, `chore/`, `ci/`, `test/`, `perf/`.

## Title & description

- [ ] PR title follows [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
      Example: `feat(engine): add pagination to the trades endpoint`.
- [ ] Description explains **what** changed and **why**, not just the diff.
- [ ] Linked issue if one exists (`Closes #123`).

## Scope

- [ ] One logical change per PR. Don't bundle unrelated refactors.
- [ ] Public API / interface changes are called out explicitly in the
      description.
- [ ] Breaking changes use `!` in the title and a `BREAKING CHANGE:` footer.

## Code

- [ ] Follows the project's structure and conventions (see
      [architecture.md](architecture.md)).
- [ ] No new direct dependencies without a one-line justification in the PR.
- [ ] No secrets, credentials, or large binaries committed.

## Tests

- [ ] New behavior has tests; bug fixes have a regression test.
- [ ] Lint + tests pass locally (the same commands CI runs):
      `cd engine && uv run ruff check . && uv run pytest`
      `cd web && npm run lint && npm run build`.

## Schema sync

- [ ] If you changed an engine API endpoint or model, the OpenAPI schema and
      generated TypeScript types are regenerated and committed:
      `cd engine && uv run python export_openapi.py`
      `cd web && npm run gen:api`.
- [ ] Any DB schema change ships an Alembic migration.

## Docs

- [ ] README / docs updated if user-facing behavior changed.
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if notable.

## CI

- [ ] All required checks are green.
- [ ] No skipped jobs without an explanation in the PR.

## After merge

- Maintainers merge with a **merge commit** (not squash). The PR title becomes
  the merge commit message (so it must be a valid Conventional Commit), and
  every commit on the branch is preserved on `test`.
- The automated `test → main` PR picks the change up on the next green run.

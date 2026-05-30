---
name: create-github-issue
description: >-
  Turn a planned process into tracked GitHub work in the Capital repo. For each
  task in a plan, create a GitHub issue (filled from the bug/feature template,
  with type:/area:/phase: labels and the current user as assignee), cut an
  issue-numbered branch from `test`, post a running log of major steps and solved
  problems as issue comments, run the pre-PR checks, and open a PR targeting
  `test` when done. Use whenever the user types /create-github-issue, asks to
  "create issues for these tasks", "track this plan as issues", "open an issue
  and start working on it", or wants the plan→issue→branch→PR workflow with a
  detailed work log.
---

# create-github-issue (Capital)

Convert a plan into tracked, logged GitHub work. The lifecycle for **each task** is:

```
plan ─▶ issue (labelled, assigned, on board) ─▶ branch (from test) ─▶ work + comment log ─▶ checks ─▶ PR → test ─▶ summary comment
```

The **issue is the single source of truth**: it accumulates a detailed log of completed parts and
solved problems as comments while the work proceeds, so anyone reading it later sees the full story.

These values are this repo's real conventions (CONTRIBUTING.md, `.github/`). If any of them have
changed since this was written, the repo files win — re-check `gh label list`,
`.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`, and `.github/rulesets/main.json`.

## 0. Preconditions

Run these read-only checks first:

1. `gh auth status` — confirm the GitHub CLI is authenticated (else stop: user runs `gh auth login`).
2. `gh api user -q .login` — the current user's login. **This is the assignee** for every issue and PR (`@me`).
3. `git fetch origin` — sync refs.
4. **Ensure the `test` base branch exists** (PRs target it). Create it from `main` if missing:
   ```bash
   if ! git ls-remote --exit-code --heads origin test >/dev/null 2>&1; then
     git push origin origin/main:refs/heads/test    # create remote `test` from main
   fi
   git fetch origin
   ```

State one line back to the user: assignee, that `test` exists/was created, then continue.

## 1. Plan → tasks

Reuse the plan already in the conversation, or work with the user to break the goal into **discrete,
independently shippable tasks** — one issue per task, each small enough to map to one branch and one
PR. **Confirm the task list with the user before creating issues** (creating issues is outward-facing).

## 2. Create one issue per task

For each task, fill the matching issue template and apply labels:

- **Kind → `type:` label + template:**
  - bug → template `bug_report.yml`, label `type:fix`
  - feature/improvement → template `feature_request.yml`, label `type:feat`
  - other → label `type:chore` / `type:docs` / `type:refactor` / `type:ci` / `type:test` as fits.
- **`area:` label** (required by the template's Area field): one of
  `area:engine`, `area:web`, `area:ci`, `area:infra`, `area:auth`, `area:ai`, `area:trading`.
- **`phase:` label**: pick the relevant `phase:phase-0` … `phase:phase-6` (ask the user if unclear).
- **Title:** concise, imperative, Conventional-Commit-flavoured, e.g. `feat(engine): add retry backoff`.
- **Body:** fill **every required template field** with real detail from the plan:
  - bug: *What happened?*, *Expected behaviour*, *Steps to reproduce*, *Area*, *Logs / environment*.
  - feature: *Problem / motivation*, *Proposed solution*, *Area*, *Alternatives considered*.
  - End the body with an acceptance-criteria checklist of sub-steps — the skeleton the work log hangs off.
- **Assignee:** `@me`.

```bash
gh issue create \
  --title "feat(engine): add retry backoff" \
  --body-file <(cat <<'EOF'
### Problem / motivation
...
### Proposed solution
...
### Area
engine
### Alternatives considered
...

### Acceptance criteria
- [ ] ...
- [ ] ...
EOF
) \
  --label "type:feat" --label "area:engine" --label "phase:phase-2" \
  --assignee "@me"
```

Capture each issue number/URL and report the created issues to the user.

## 3. Take on an issue → branch + board

Do one issue at a time unless told to batch.

1. Add the issue to the **Capital** project board and move it to **In Progress**:
   ```bash
   gh issue edit <n> --add-project "Capital"
   # then set Status → In Progress (discover field/option ids once):
   #   gh project list --owner FurkanEdizkan
   #   gh project field-list <project-number> --owner FurkanEdizkan   # find "Status" field + "In Progress" option ids
   #   gh project item-edit --id <item-id> --field-id <status-field-id> --single-select-option-id <in-progress-id> --project-id <project-id>
   ```
   If the board can't be reached non-interactively, note it and continue — don't block the work on it.
2. Cut the branch **from `test`**, named per repo rule `<type>/<issue#>-<short-slug>`
   (types: `feat fix chore docs refactor test ci`):
   ```bash
   git switch -c feat/142-retry-backoff origin/test
   ```
3. Post a **"work started"** comment so the log opens with a start marker:
   ```bash
   gh issue comment <n> --body "🚧 Started on branch \`feat/142-retry-backoff\` (from \`test\`)."
   ```

## 4. Work the task → log as you go

The issue comments are the **detailed log**. Comment at every meaningful boundary — don't wait for the end:

- **Major step done** → what was done and why (e.g. "✅ Added exponential backoff to `Client.request`; covered by `test_retry_backoff`").
- **Problem hit & solved** → symptom, root cause, fix. These solved-issue notes are the most valuable part of the log.
- **Decision / scope change** → the choice and the reasoning.

```bash
gh issue comment <n> --body "✅ <step>" # or "🐛 <problem> → <fix>"
```

Commit with **Conventional Commits** — invoke the `conventional-commits` skill for this repo's exact
format (commitlint @config-conventional + husky + CI reject bad messages). Reference the issue in the
summary/body (`(#142)`). Keep commits focused so history mirrors the comment log. Tick the issue
checklist as sub-steps land (`gh issue edit <n> --body ...`).

## 5. Pre-PR checks (must pass)

Run the same checks CI requires before opening the PR; fix red before proceeding:

```bash
cd engine && uv run ruff check . && uv run pytest        # engine — lint, migrate, test
cd web    && npm run lint && npm run build               # web — lint, typecheck, build
```

- Include an **Alembic migration** for any DB schema change.
- If an engine API endpoint/model changed, **regenerate the schema** so CI's drift check passes:
  ```bash
  cd engine && uv run python export_openapi.py   # updates web/openapi.json
  cd web    && npm run gen:api                    # updates src/lib/api/schema.d.ts
  ```

Required status checks on merge target: `engine — lint, migrate, test`, `web — lint, typecheck, build`,
`docker — images build`.

## 6. Complete → PR to `test`

1. Push: `git push -u origin <branch>`.
2. Open the PR **with base `test`**, body reproducing **every section** of `PULL_REQUEST_TEMPLATE.md`
   (`## Summary`, `## Type of change`, `## Testing`, `## Checklist`, `Closes #<n>`), assignee `@me`:
   ```bash
   gh pr create --base test --head <branch> \
     --title "feat(engine): add retry backoff" \
     --body-file <(cat <<'EOF'
## Summary
...
## Type of change
- [x] feat — new feature
## Testing
ruff + pytest pass; npm run lint + build pass. ...
## Checklist
- [x] Tests and lint pass locally
- [ ] An Alembic migration is included for any DB schema change
- [x] Docs / README updated if behaviour changed
- [x] PR title follows Conventional Commits

Closes #142
EOF
) \
     --assignee "@me"
   ```
   - Fill the checklist **honestly** (only tick what's true).
   - ⚠️ **Auto-close caveat:** `Closes #142` only auto-closes the issue when the PR merges into the
     **default branch (`main`)**. Since this PR targets `test`, the issue will **not** auto-close on
     merge — close it manually (`gh issue close 142`) once merged, after posting the summary comment.
3. Post a **final summary comment** on the issue: a tidy recap of completed parts and every problem
   solved, plus the PR link — this closes the log:
   ```bash
   gh issue comment <n> --body "🎉 Completed in #<pr-number>. Summary: …"
   ```

Report each PR URL to the user. **Do not merge** — `main`/`test` land via PR review (1 approval
required on `main`); the repo admin self-merges solo work. Merges use a **merge commit** (not squash)
and the branch is deleted afterward.

## Conventions checklist (per task)

- [ ] Issue from the right template; `type:` + `area:` + `phase:` labels; assigned to user
- [ ] Issue on the Capital board, moved to In Progress
- [ ] Branch `<type>/<issue#>-<slug>`, cut from `test`
- [ ] "Started" comment posted
- [ ] Major steps + solved problems logged as comments
- [ ] Conventional commits referencing the issue
- [ ] Pre-PR checks pass (ruff/pytest, lint/build, migration, openapi regen)
- [ ] PR against `test`, template filled honestly, assigned, `Closes #<n>`
- [ ] Final summary comment posted with the PR link; issue closed manually after merge to `test`

## Notes

- **Non-destructive:** never merges, force-pushes, or deletes branches without an explicit ask.
- If a repo rule conflicts with these steps, **the repo file wins** — surface the conflict and follow it.
- Default to creating all issues up front, then taking them on one branch/PR at a time; follow the
  user's stated preference if different.

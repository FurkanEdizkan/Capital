# Branching model

Capital uses a **two-trunk** model: a stable `main` and an integration `test`.
Contributors never touch `main` directly — it is promoted from `test`
automatically once CI is green.

```text
contributors  ->  feature/*  ->  PR into test  ->  CI green  ->  merged into test
                                                                       |
                                                          automated PR test -> main
                                                                       |
                                                                  CI green
                                                                       v
                                                                main (stable)
```

- **`main`** — stable. Releases are tagged from here. Never PR directly into it.
- **`test`** — integration. All contributor PRs target `test`.
- **`feature/*`** — short-lived topic branches off `test`
  (`feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `ci/`, `test/`, `perf/`).

When CI on `test` is green, [`promote-to-main.yml`](../.github/workflows/promote-to-main.yml)
opens (or refreshes) a single PR from `test` into `main`. Maintainers review and
merge it to ship.

---

## One-time maintainer setup

The automation is **inert until these are configured.**

### 1. Create the `test` branch

Create `test` from `main` and push it:

```sh
git switch -c test
git push -u origin test
```

### 2. Add the `PROMOTE_TOKEN` secret

`promote-to-main.yml` creates the promotion PR with a Personal Access Token,
not the default `GITHUB_TOKEN`. The default token (a) can't open PRs when
"Allow GitHub Actions to create and approve pull requests" is off, and (b)
wouldn't trigger the required CI/commitlint checks on the PR it opens, leaving
it permanently un-mergeable.

1. Create a **fine-grained PAT** scoped to this repo with
   **Contents: Read** and **Pull requests: Read and write**.
2. Add it under **Settings → Secrets and variables → Actions →
   New repository secret**, named exactly **`PROMOTE_TOKEN`**.

### 3. Protect `main` (and optionally `test`)

Under **Settings → Branches → Branch protection rules**, add a rule for `main`:

- [ ] **Require a pull request before merging.**
- [ ] **Require status checks to pass before merging.** Add the CI checks as
      required (use the check *display names*, e.g. `engine — lint, migrate, test`,
      `web — lint, typecheck, build`, `docker — images build`, and
      `Validate PR title` from the Commitlint workflow).
- [ ] **Allowed merge methods: Merge commit only** — disable Squash and Rebase,
      so every PR lands as a merge commit and history stays fully traceable.
- [ ] **Do not require linear history** — the model relies on merge commits.
- [ ] **Restrict who can push to matching branches** — allow only
      `github-actions[bot]` (and yourself) so the promotion automation can push
      while everyone else stays PR-only.
- [ ] If you're the sole maintainer, **do not** require approval from a separate
      reviewer — that would block you from merging your own promotion PRs.

The same rule on `test` is optional but recommended (require PR + CI green) so
nothing can bypass the `test → main` chain.

---

## Day-to-day flow

```sh
git switch test
git pull
git switch -c feat/my-thing
# ...work...
git push -u origin feat/my-thing
gh pr create --base test        # never --base main
```

Maintainers merge green PRs into `test` with a merge commit; the promotion PR
picks the change up on the next green run.

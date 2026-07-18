# Vendored Claude Code skills

The skills in this directory are **committed to the repo on purpose** so that
every contributor — and every AI agent working in Capital — has them available
on clone, with no plugin install, no `npx`, and no network access. In
particular, the `conventional-commits` and `conventional-branches` skills mean
any agent can read them and produce commits/branches in our conventional style
without extra setup.

`.claude/` is otherwise gitignored (see the root `.gitignore`); only the skill
folders listed below and `skills-lock.json` are un-ignored and tracked.

## What's here

| Skill | Upstream source | License |
| ----- | --------------- | ------- |
| `conventional-commits` | [FurkanEdizkan/My-Skills](https://github.com/FurkanEdizkan/My-Skills) | Apache-2.0 |
| `conventional-branches` | [FurkanEdizkan/My-Skills](https://github.com/FurkanEdizkan/My-Skills) | Apache-2.0 |
| `design-taste-frontend` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT (see its `LICENSE` + `ATTRIBUTION.md`) |

Exact upstream commit, path, and content hash for each skill are pinned in
[`skills-lock.json`](skills-lock.json).

## Checking / updating versions

Versions are tracked in `skills-lock.json` and managed by
[`scripts/skills-sync.mjs`](../../scripts/skills-sync.mjs) (Node, no
dependencies). Updating is **opt-in** — it is never wired into a git hook, so a
new upstream release can't block anyone's commit.

```sh
npm run skills:check              # report which skills have upstream updates
npm run skills:update             # pull the latest for all (asks before writing)
npm run skills:update -- conventional-commits   # just one
npm run skills:update -- --yes    # non-interactive (CI / scripts)
```

`skills:check` decides drift by comparing each skill's locked `sha256` against a
fresh upstream fetch (both LF), so the result never depends on your local line
endings. After `skills:update` rewrites files + the lock, review the diff and
commit it like any other change (branch off `test`, PR into `test`).

## Relationship to the My-Skills marketplace

Capital still registers the `FurkanEdizkan/My-Skills` plugin marketplace in
[`.claude/settings.json`](../settings.json), which uniquely provides the other
generalized skills (`modular-services`, `three-tier-git-flow`,
`create-github-issue`). If a contributor installs that plugin, the two
conventional skills also appear namespaced as `skills:conventional-commits` /
`skills:conventional-branches` — harmless duplicates of the always-present
vendored copies here. Dropping the two conventional skills from the marketplace
enablement to avoid that overlap is a possible future cleanup, not required.

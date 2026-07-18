# Attribution

`SKILL.md` in this directory is vendored **unmodified** from a third-party
open-source project and redistributed under its MIT license (see `LICENSE`).

- **Upstream project:** taste-skill — https://github.com/Leonxlnx/taste-skill
- **Author:** Leonxlnx
- **Upstream skill path:** `skills/taste-skill/SKILL.md`
- **Vendored source hash:** `a6d128e53b4ec0238baee751dde33bf707adb5ec`
- **License:** MIT (© 2026 Leonxlnx)

## Why it's committed here

`.claude/skills/` is otherwise gitignored in this repo (see the root
`.gitignore`), so locally-installed skills stay local. This one skill is
explicitly un-ignored and committed so every contributor gets Capital's shared
frontend-design guidance on clone — no plugin or `npx` install required.

## Updating

Upstream install command (for reference):

```sh
npx skills add Leonxlnx/taste-skill -s design-taste-frontend
```

To refresh the vendored copy, replace `SKILL.md` with the upstream version and
update the source hash above. Keep `LICENSE` intact.

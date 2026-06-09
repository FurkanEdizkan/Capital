# Releases

Capital releases are cut from **`main`**, which is only ever updated through
the automated `test → main` promotion PR (see [branching.md](branching.md)).
So "release" means: tag a green commit on `main`.

## Versioning

Use [Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH`.

- `feat:` commits since the last tag → bump **MINOR**.
- `fix:` commits → bump **PATCH**.
- A `BREAKING CHANGE:` footer or `!` in the type → bump **MAJOR**.

Pre-1.0, breaking changes may land in MINOR bumps.

## Cutting a release manually

```sh
git switch main
git pull
git tag -a v0.3.0 -m "Release v0.3.0"
git push origin v0.3.0
gh release create v0.3.0 --generate-notes
```

Update the `[Unreleased]` section of [CHANGELOG.md](../CHANGELOG.md) to the new
version as part of the release.

## Automating it

A future `release.yml` workflow can fire on tag push (`on: push: tags: ['v*']`)
and build Docker images / push to a registry. Until that lands, releases stay
manual.

# Release

How to cut a new version of llm-openrouter-decisions. Releases are published by hand: there is no publish workflow, and creating a GitHub release uploads nothing.

## Versions and tags

- Versions follow [PEP 440](https://peps.python.org/pep-0440/): `0.1a0`, `0.1`, `0.1.1`, `0.2`.
- The git tag is the bare version, without a `v` prefix (`0.1a0`), as in Simon Willison's LLM plugins.
- Alpha, beta and release candidate versions (`a`, `b`, `rc`) are published as GitHub pre-releases.
- **Patch** (`0.1` to `0.1.1`): bug fixes and docs. **Minor** (`0.1` to `0.2`): new features or behaviour changes.

## Preconditions

- On `main`, up to date, working tree clean: `git switch main && git pull && git status`.
- Any feature PR is already merged. The version bump is its own commit on `main`, made after the merge, never inside a feature PR.
- `gh` is authenticated.
- `twine` has PyPI credentials (token in `~/.pypirc` or `TWINE_USERNAME=__token__` and `TWINE_PASSWORD`).

## Steps

Replace `X.Y.Z` with the new version.

1. Set `version = "X.Y.Z"` in `pyproject.toml`.

2. Add the release notes to `LOG.md`, in English, under a `YYYY-MM-DD` heading, most recent on top.

3. Lint and test. Both must pass; stop the release if either fails:

   ```bash
   uvx ruff check .
   uv run pytest
   ```

4. Commit and tag:

   ```bash
   git add -u
   git commit -m "Release X.Y.Z"
   git tag X.Y.Z
   ```

5. Push the branch and the tag. From here on the steps are public and hard to undo:

   ```bash
   git push origin main --tags
   ```

6. Create the GitHub release, with the notes in English. Add `--prerelease` for `a`, `b` and `rc` versions:

   ```bash
   gh release create X.Y.Z --title "X.Y.Z" --notes "release notes here"
   ```

7. Build, check and publish to PyPI:

   ```bash
   rm -rf dist
   uv build
   twine check dist/*
   twine upload dist/llm_openrouter_decisions-X.Y.Z*
   ```

8. Check the published package from a clean environment:

   ```bash
   uvx --with llm-openrouter-decisions==X.Y.Z llm plugins
   ```

   The local development install (`llm install -e .`) picks up the new code by itself.

## Checklist

- [ ] On `main`, pulled, clean
- [ ] Version set in `pyproject.toml`
- [ ] `LOG.md` updated
- [ ] `uvx ruff check .` passes
- [ ] `uv run pytest` passes
- [ ] Commit and tag `X.Y.Z`
- [ ] Pushed with tags
- [ ] GitHub release created (pre-release for `a`, `b`, `rc`)
- [ ] Built, checked and uploaded with twine
- [ ] Published package checked with `uvx`

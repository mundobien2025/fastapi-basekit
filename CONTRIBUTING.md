# Contributing to fastapi-basekit

Thanks for contributing. This document covers the bare minimum to keep the
repo history professional and the release flow predictable. For the full
guide (setup, tests, release process), see
[docs/contributing.md](https://mundobien2025.github.io/fastapi-basekit/contributing/).

---

## Commit message format

We use **[Conventional Commits](https://www.conventionalcommits.org/)**.
The `commit-msg` hook rejects messages that don't match.

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Allowed types

| Type | Use when |
|------|----------|
| `feat` | New user-visible functionality |
| `fix` | Bug affecting documented behavior |
| `docs` | README, `docs/`, docstrings, CHANGELOG |
| `refactor` | Restructure, no behavior change |
| `perf` | Performance improvement |
| `test` | Tests only, no production code changes |
| `build` | `pyproject.toml`, requirements, packaging |
| `ci` | `.github/workflows/`, release scripts |
| `chore` | Maintenance (version bumps, renames, gitignore) |
| `style` | Formatting (black, isort) — no functional change |
| `revert` | Revert a previous commit |

### Subject rules

- Imperative present: `add X`, not `added X` / `adds X`
- Lowercase, no trailing period
- ≤ 72 characters
- English (international audience)
- Scope optional but recommended: `feat(beanie):`, `fix(repository):`

### Body rules (optional)

- Blank line between subject and body
- Wrap at 72 chars
- Explain **why**, not **what** (the diff already shows the what)
- Issue refs at footer: `Closes #N`, `Refs #N`

### Examples

```
✓ feat(beanie): add build_list_pipeline + build_list_queryset hooks

  Beanie equivalent of SQLAlchemy's build_list_queryset, plus a parallel
  build_list_pipeline hook for cross-collection joins via $lookup. Both
  overrideable at repo or service level.

  Closes #42

✓ fix(repository): coerce str → ObjectId in Link.id filters
✓ docs(api-reference): document use_aggregation service flag
✓ chore: bump version to 0.3.2
✓ build: pin setuptools to emit Core Metadata 2.3
✓ refactor(service): extract _build_match_stage helper

✗ feature: add stuff              ← wrong type spelling + vague
✗ fix: changes                    ← not a fix + meaningless
✗ add version                     ← missing type + vague
✗ Update README.md                ← GitHub UI auto-commit
```

---

## Setup

```bash
git clone https://github.com/mundobien2025/fastapi-basekit
cd fastapi-basekit

# Install dev deps
python -m venv .venv && source .venv/bin/activate
pip install -e .[all]
pip install -r requirements-dev.txt

# Activate commit message template + hook
git config --local commit.template .gitmessage
pip install pre-commit
pre-commit install --hook-type commit-msg
```

After setup, `git commit` (no `-m`) opens the editor with the template.
The `commit-msg` hook rejects messages that don't match the spec.

---

## Branch naming

- `feat/<short-description>` — new features
- `fix/<bug-id-or-description>` — bugfixes
- `docs/<area>` — docs only
- `chore/<description>` — maintenance

---

## Pull requests

- PR title: same format as a commit subject
- Description: context + changes + test plan + breaking changes (if any)
- Link to issue: `Closes #N`
- Tests required for `feat:` and `fix:`

---

## Versioning + release

Semver. Bumps in `pyproject.toml` + `plugin.json` + `marketplace.json` +
`CHANGELOG.md`. Use `make release V=X.Y.Z` to automate. See
[`RELEASING.md`](RELEASING.md) for the maintainer flow.

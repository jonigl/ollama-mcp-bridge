# GitHub Workflows Documentation

This document describes the GitHub workflows set up for the ollama-mcp-bridge project.

## Available Workflows

### 1. Tests (`test.yml`)

**Trigger:** Push to `main` or `develop` branches, or pull requests to `main`.

**Purpose:** Runs unit tests and validates basic functionality.

**Key Features:**
- Uses `uv` for Python dependency management
- Runs pytest unit tests
- Verifies import functionality
- Checks version detection

### 2. TestPyPI Publish (`test-pypi-publish.yml`)

**Trigger:** Tags matching `v*a*`, `v*b*`, or `v*rc*` (alpha, beta, release candidates)

**Purpose:** Publishes packages to TestPyPI for verification.

**Key Features:**
- Builds the package with `build`
- Validates package with `twine check`
- Verifies the version matches the git tag
- Publishes to TestPyPI
- Tests installation from TestPyPI with retry logic
- Uploads built packages as artifacts for inspection

### 4. Release to PyPI (`release.yml`)

**Trigger:** Tags starting with `v*`

**Purpose:** Official release process for publishing to PyPI.

**Key Features:**
- Two-stage process: test publish to TestPyPI first
- If successful, publishes to PyPI
- Handles trusted publishing with GitHub OIDC tokens

## Tag Naming Conventions

- **Production releases:** `v1.0.0`, `v1.1.0`, etc.
- **Pre-releases (PEP 440 compliant):**
  - Release candidates: `v1.0.0rc1`, `v1.0.0rc2`, etc.
  - Beta releases: `v1.0.0b1`, `v1.0.0b2`, etc.
  - Alpha releases: `v1.0.0a1`, `v1.0.0a2`, etc.

## Required Secrets

- `TEST_PYPI_API_TOKEN`: API token for TestPyPI
- `PYPI_API_TOKEN`: API token for PyPI

## PEP 440 Compliance

All version tags must be PEP 440 compliant to work with setuptools_scm. This means:

- No hyphens in version numbers
- Use `a` for alpha, `b` for beta, `rc` for release candidates
- Examples: `v1.0.0a1`, `v1.0.0b1`, `v1.0.0rc1`

## Dependabot Configuration

Dependabot is configured to check for updates to dependencies weekly using the `uv` package ecosystem.

## Usage Examples

### Creating an alpha release (for TestPyPI):
```bash
git tag v1.0.0a1
git push origin v1.0.0a1
```

### Creating a beta release:
```bash
git tag v1.0.0b1
git push origin v1.0.0b1
```

### Creating a release candidate:
```bash
git tag v1.0.0rc1
git push origin v1.0.0rc1
```

### Creating a production release:
```bash
git tag v1.0.0
git push origin v1.0.0
```

## Release Process

After pushing a tag, the corresponding workflow will be triggered automatically. GitHub releases (including release notes and changelog) are manually created using the GitHub web interface after the tag is created and the workflow completes successfully.

### Future Improvements

In the future, we plan to:
1. Automate the generation of release notes and changelogs
2. Implement conventional commit practices for automated semantic versioning (semver)
3. Integrate tools like semantic-release to fully automate the release process based on commit messages

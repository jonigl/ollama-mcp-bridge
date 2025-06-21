# GitHub Workflows Documentation

This document describes the GitHub workflows set up for the ollama-mcp-bridge project.

## Available Workflows

### 1. Tests ([test.yml](.github/workflows/test.yml))

**Trigger:**
- Push to `main` branch
- Pull requests to `main` branch
- Ignores changes to docs, images, and some config files

**Purpose:**
Runs unit tests using `pytest` in a fresh environment managed by `uv`.

**Key Steps:**
- Checkout code
- Set up Python and `uv`
- Sync dependencies
- Run `pytest` on `tests/test_unit.py`

---

### 2. Test Publish ([test-publish.yml](.github/workflows/test-publish.yml))

**Trigger:**
- Push of tags matching `vX.Y.Z` (e.g., `v1.0.0`)
- Pushes to the `fix/build-system-and-ci` branch (for testing)

**Purpose:**
Builds the package and publishes it to **TestPyPI** for verification.

**Key Steps:**
- Checkout code
- Set up Python and `uv`
- Build the package
- Publish to TestPyPI using `pypa/gh-action-pypi-publish` with the TestPyPI repository URL

---

### 3. Publish ([publish.yml](.github/workflows/publish.yml))

**Trigger:**
- When a GitHub Release is created

**Purpose:**
Builds the package and publishes it to **PyPI**.

**Key Steps:**
- Checkout code
- Set up Python and `uv`
- Build the package
- Publish to PyPI using `pypa/gh-action-pypi-publish`
- Upload built distributions to the GitHub Release as artifacts

---

## Tag Naming Conventions

- **Production releases:** `v1.0.0`, `v1.1.0`, etc.
- **Pre-releases:** Not currently handled by workflows (see below)

> **Note:** Only tags matching `vX.Y.Z` will trigger TestPyPI publishing. Pre-release tags (like `v1.0.0a1`) are not currently matched by the workflow.

## Required Secrets

- For PyPI: OIDC is used (no token needed if using trusted publishing)
- For TestPyPI: OIDC is used (no token needed if using trusted publishing)

## Usage Examples

### Creating a release (for PyPI and TestPyPI):

```bash
git tag v1.0.0
git push origin v1.0.0
```

### Creating a GitHub Release (for PyPI):

- Go to the GitHub Releases page and create a new release for your tag.

---

## Testing Your Package from TestPyPI

To verify your package installation from TestPyPI:

```bash
# Create a fresh virtual environment
python -m venv test_venv
source test_venv/bin/activate  # On macOS/Linux
# Or on Windows: test_venv\Scripts\activate

# Install dependencies first from PyPI
pip install fastapi httpx loguru mcp typer uvicorn

# Install your package from TestPyPI with --no-deps
pip install --index-url https://test.pypi.org/simple/ --no-deps ollama-mcp-bridge

# Test the CLI command
ollama-mcp-bridge --version
```

---

## Release Process

- Push a tag like `v1.0.0` to trigger TestPyPI publish.
- Create a GitHub Release to trigger PyPI publish.
- Artifacts are uploaded to the GitHub Release.

---

## Future Improvements

- Add support for pre-release tags (alpha, beta, rc) in workflows.
- Automate changelog and release note generation.
- Integrate semantic-release or similar tools

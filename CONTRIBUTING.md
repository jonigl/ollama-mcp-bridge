# Contributing to ollama-mcp-bridge

## Development Setup

```bash
# Clone the repository
git clone https://github.com/jonigl/ollama-mcp-bridge.git
cd ollama-mcp-bridge

# Install dependencies (including dev tools)
uv sync
```

## Code Formatting

We use [Black](https://black.readthedocs.io/) for consistent code formatting with a 120-character line length.

```bash
# Format all code
black .

# Check formatting without changes
black --check .
```

Black is configured in `pyproject.toml` and runs automatically when installed via `uv sync`.

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_unit.py -v

# Run tests in quiet mode
uv run pytest -q

# Run with verbose output
uv run pytest -v
```

## Environment Variables

For testing timeout behavior, you can set:

```bash
# Set custom Ollama proxy timeout (milliseconds)
OLLAMA_PROXY_TIMEOUT=600000 uv run pytest

# Disable timeouts (useful for debugging)
OLLAMA_PROXY_TIMEOUT=0 uv run pytest
```

## Before Committing

1. **Format your code**: `black .`
2. **Run tests**: `uv run pytest`
3. **Verify all tests pass**

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code formatting (no functional changes)
- `refactor:` Code restructuring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### Example Commits

```bash
feat: add OLLAMA_PROXY_TIMEOUT environment variable for configurable HTTP timeouts

fix: resolve timeout issues with large models on localhost

docs: update README with new environment variable documentation

style: apply black formatting to test files

test: add comprehensive timeout behavior test coverage
```

## Adding New Features

1. Create a feature branch: `git checkout -b feat/your-feature-name`
2. Implement your changes with tests
3. Format code: `black .`
4. Run tests: `uv run pytest`
5. Commit with conventional commit message
6. Push and create a pull request

## Questions?

Open an issue on [GitHub](https://github.com/jonigl/ollama-mcp-bridge/issues) if you have questions or need help.

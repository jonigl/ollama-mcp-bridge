FROM python:3.10.15-slim

RUN pip install uv

ARG VERSION=0.1.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_OLLAMA_MCP_BRIDGE=${VERSION}

COPY . ./

# Install all dependencies from lockfile (without building the project)
RUN uv sync --frozen --no-install-project

# Install build deps, then install the project without build isolation
# so the SETUPTOOLS_SCM_PRETEND_VERSION env var is visible to setuptools-scm
RUN uv pip install hatchling hatch-vcs setuptools-scm && \
    uv pip install --no-build-isolation --no-deps .

EXPOSE 8000

CMD ["uv", "run", "ollama-mcp-bridge"]

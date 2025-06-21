"""Ollama MCP Bridge package."""

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0.dev0"  # Fallback version when not installed from package

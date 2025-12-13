import os
import sys
from pathlib import Path

# Add src directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ollama_mcp_bridge.utils import expand_env_vars, expand_dict_env_vars


def test_expand_env_vars():
    os.environ["TEST_VAR"] = "test_value"

    assert expand_env_vars("normal string") == "normal string"
    assert expand_env_vars("${env:TEST_VAR}") == "test_value"
    assert expand_env_vars("prefix ${env:TEST_VAR} suffix") == "prefix test_value suffix"

    cwd = os.getcwd()
    assert expand_env_vars("${workspaceFolder}") == cwd

    custom_cwd = "/tmp/custom"
    assert expand_env_vars("${workspaceFolder}", cwd=custom_cwd) == custom_cwd


def test_expand_dict_env_vars():
    os.environ["TEST_VAR"] = "test_value"
    cwd = os.getcwd()

    data = {
        "key1": "value1",
        "key2": "${env:TEST_VAR}",
        "key3": ["item1", "${workspaceFolder}"],
        "key4": {"nested": "${env:TEST_VAR}"},
    }

    expanded = expand_dict_env_vars(data)

    assert expanded["key1"] == "value1"
    assert expanded["key2"] == "test_value"
    assert expanded["key3"] == ["item1", cwd]
    assert expanded["key4"]["nested"] == "test_value"

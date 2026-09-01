import pytest
from orchestration.tools import (
    ToolRegistry,
    tool_registry,
    tool,
    ToolDefinition,
)

def test_custom_registry_registration():
    registry = ToolRegistry()

    @registry.register(name="custom_add", description="Adds two numbers.", category="math")
    def add(a: int, b: int = 5) -> int:
        """Adds two numbers docstring."""
        return a + b

    defn = registry.get_tool_definition("custom_add")
    assert defn is not None
    assert defn.name == "custom_add"
    assert defn.description == "Adds two numbers."
    assert defn.category == "math"
    assert "a" in defn.parameters_schema
    assert defn.parameters_schema["a"]["required"] is True
    assert defn.parameters_schema["b"]["required"] is False
    assert defn.parameters_schema["b"]["default"] == 5

    # Test execution
    res = registry.execute("custom_add", a=10, b=20)
    assert res == 30

    # Test default param execution
    res_default = registry.execute("custom_add", a=10)
    assert res_default == 15

def test_bare_decorator_registration():
    registry = ToolRegistry()

    @registry.register
    def sample_func(x: str) -> str:
        """Sample function docstring."""
        return f"Echo: {x}"

    assert registry.get_tool("sample_func") is not None
    defn = registry.get_tool_definition("sample_func")
    assert defn.description == "Sample function docstring."
    assert defn.category == "general"

    res = registry.execute("sample_func", x="hello")
    assert res == "Echo: hello"

def test_get_tools_by_names():
    registry = ToolRegistry()

    @registry.register
    def tool_one():
        return 1

    @registry.register
    def tool_two():
        return 2

    funcs = registry.get_tools_by_names(["tool_one", "tool_two", "non_existent"])
    assert len(funcs) == 2
    assert funcs[0]() == 1
    assert funcs[1]() == 2

def test_execute_unregistered_tool():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="Tool unknown_tool not registered"):
        registry.execute("unknown_tool")

def test_global_tool_registry():
    @tool(name="test_global_echo", category="test")
    def echo_message(msg: str) -> str:
        return f"Test: {msg}"

    assert tool_registry.get_tool("test_global_echo") is not None
    assert tool_registry.execute("test_global_echo", msg="riva") == "Test: riva"

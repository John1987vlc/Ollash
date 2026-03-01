import pytest
from backend.utils.core.tools.tool_decorator import get_discovered_definitions


@pytest.mark.manual
def test_validate_all_tool_definitions():
    """
    Manual test to verify that all discovered tools have a valid JSON schema
    compatible with Ollama's tool calling API.
    """
    definitions = get_discovered_definitions()
    errors = []

    for tool in definitions:
        name = tool.get("function", {}).get("name")
        params = tool.get("function", {}).get("parameters", {})

        # Ollama expects 'properties' to be an object, not a string or empty
        properties = params.get("properties")

        print(f"Checking tool: {name}...")

        if properties is not None and not isinstance(properties, dict):
            errors.append(f"Tool '{name}': 'properties' must be a dict, got {type(properties)}")
            continue

        if not properties and params.get("type") == "object":
            # Some models fail if type is object but properties is empty
            print(f"  Warning: Tool '{name}' has empty properties.")

    if errors:
        pytest.fail("\n".join(errors))
    else:
        print("\n✅ All tool definitions are structurally valid.")


if __name__ == "__main__":
    # To run: pytest tests/manual/test_tool_definitions.py -m manual -s
    pass

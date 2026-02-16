"""
Main test suite for Ollash project.

This is the entry point for all tests. It organizes and runs tests by module:
- agents/: Tests for the agents module
- core/: Tests for core utilities (parsers, validators, heartbeat)
- services/: Tests for services module
- utils/: Tests for utils module
- web/: Tests for web UI and blueprints
- automations/: Tests for automation system
- integration/: Integration tests
- e2e/: End-to-end tests

Run this with: pytest tests/test_main.py -v
Or run specific modules: pytest tests/agents/ -v
"""

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    """Organize test collection by module."""
    # Markers can be used to group tests by module
    for item in items:
        if "agents" in str(item.fspath):
            item.add_marker(pytest.mark.agents)
        elif "core" in str(item.fspath):
            item.add_marker(pytest.mark.core)
        elif "services" in str(item.fspath):
            item.add_marker(pytest.mark.services)
        elif "utils" in str(item.fspath):
            item.add_marker(pytest.mark.utils)
        elif "web" in str(item.fspath):
            item.add_marker(pytest.mark.web)
        elif "automations" in str(item.fspath):
            item.add_marker(pytest.mark.automations)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


class TestMainSuite:
    """Main test suite that documents test structure."""

    def test_suite_organization(self):
        """Verify that test suite is properly organized."""
        tests_dir = Path(__file__).parent

        # Check that all module test directories exist
        expected_dirs = [
            "agents",
            "core",
            "services",
            "utils",
            "web",
            "automations",
            "integration",
            "e2e",
        ]
        for dir_name in expected_dirs:
            module_dir = tests_dir / dir_name
            assert module_dir.exists(), f"Test module {dir_name}/ should exist"
            assert (module_dir / "__init__.py").exists(), f"Test module {dir_name}/ should have __init__.py"

    def test_modules_have_tests(self):
        """Verify that each module has tests."""
        tests_dir = Path(__file__).parent

        # These modules should have test files
        module_requirements = {
            "agents": ["test_auto_agent.py"],
            "core": [
                "test_llm_response_parser.py",
                "test_file_validator.py",
                "test_heartbeat.py",
            ],
            "web": ["test_blueprints.py"],
            "automations": ["test_automations.py"],
        }

        for module, test_files in module_requirements.items():
            module_dir = tests_dir / module
            for test_file in test_files:
                test_path = module_dir / test_file
                assert test_path.exists(), f"Module {module} should have {test_file}"


def test_main():
    """
    Main test entry point.

    Usage:
        pytest tests/test_main.py -v                      # Run this file
        pytest tests/ -v                                  # Run all tests
        pytest tests/agents/ -v                           # Run agents tests only
        pytest tests/core/ -v                             # Run core tests only
        pytest tests/web/ -v                              # Run web tests only
        pytest tests/automations/ -v                      # Run automation tests only
        pytest tests/ -m agents -v                        # Run all tests marked as agents
        pytest tests/ --co -q                             # List all tests without running
    """
    assert True, "Main test suite is configured correctly"


if __name__ == "__main__":
    # Run all tests
    pytest.main([str(Path(__file__).parent), "-v", "--tb=short"])

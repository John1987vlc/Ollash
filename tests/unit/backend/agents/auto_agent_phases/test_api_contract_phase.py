"""Unit tests for ApiContractPhase."""

from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.api_contract_phase import ApiContractPhase

_VALID_YAML = """\
openapi: "3.0.3"
info:
  title: Test API
  version: "1.0"
paths:
  /users:
    get:
      summary: List users
      responses:
        "200":
          description: OK
"""


@pytest.mark.unit
class TestApiContractPhase:
    def _make_context(self, framework="fastapi", project_type="backend"):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.logic_plan = {
            "app/main.py": {"purpose": "Entry point", "exports": ["app"]},
        }
        ctx.api_contract = None
        ctx.api_endpoints = []
        ctx.file_manager = MagicMock()

        tech = MagicMock()
        tech.framework = framework
        ctx.tech_stack_info = tech

        ptype = MagicMock()
        ptype.project_type = project_type
        ctx.project_type_info = ptype

        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": _VALID_YAML},
            {},
        )
        ctx.response_parser = MagicMock()
        return ctx

    @pytest.mark.asyncio
    async def test_generates_openapi_for_backend(self, tmp_path):
        ctx = self._make_context(framework="fastapi")
        phase = ApiContractPhase(ctx)
        gf, struct, fps = await phase.run("REST API", "myapi", tmp_path, "", {}, {}, [])
        assert "openapi.yaml" in gf
        assert "openapi: " in gf["openapi.yaml"]
        assert ctx.api_contract is not None
        assert len(ctx.api_endpoints) >= 1

    @pytest.mark.asyncio
    async def test_skips_non_backend_project(self, tmp_path):
        ctx = self._make_context(framework="pygame", project_type="cli")
        phase = ApiContractPhase(ctx)
        gf, _, _ = await phase.run("CLI tool", "mytool", tmp_path, "", {}, {}, [])
        assert "openapi.yaml" not in gf
        assert ctx.api_contract is None

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, tmp_path):
        ctx = self._make_context()
        fenced = f"```yaml\n{_VALID_YAML}\n```"
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": fenced},
            {},
        )
        phase = ApiContractPhase(ctx)
        gf, _, _ = await phase.run("REST API", "myapi", tmp_path, "", {}, {}, [])
        # Should have stripped fences and produced valid YAML
        assert ctx.api_contract is not None
        assert "```" not in ctx.api_contract

    @pytest.mark.asyncio
    async def test_retries_on_invalid_yaml(self, tmp_path):
        ctx = self._make_context()
        call_count = [0]

        def _chat(*a, **kw):
            call_count[0] += 1
            if call_count[0] < 3:
                return ({"content": "not valid yaml {{{{"}, {})
            return ({"content": _VALID_YAML}, {})

        ctx.llm_manager.get_client.return_value.chat.side_effect = _chat
        phase = ApiContractPhase(ctx)
        gf, _, _ = await phase.run("REST API", "myapi", tmp_path, "", {}, {}, [])
        assert call_count[0] == 3
        assert "openapi.yaml" in gf

    def test_extract_endpoints(self):
        endpoints = ApiContractPhase._extract_endpoints(_VALID_YAML)
        assert len(endpoints) == 1
        assert endpoints[0]["path"] == "/users"
        assert endpoints[0]["method"] == "GET"

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

@pytest.mark.asyncio
async def test_execution_loop_with_retries():
    # 1. Setup Mocks
    mock_context = MagicMock()
    mock_context.logger = MagicMock()
    mock_context.event_publisher = MagicMock()
    mock_context.file_manager = MagicMock()
    mock_context.llm_manager = MagicMock()
    mock_context.select_related_files.return_value = {}
    
    # Mock Validator
    mock_validator = MagicMock()
    mock_validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))
    mock_context.files_ctx.validator = mock_validator
    
    # Mock Backlog
    mock_context.backlog = [
        {"id": "T1", "title": "Test Task", "file_path": "test.py", "task_type": "create_file"}
    ]
    
    # 2. Mock LLM Response (Fail twice, then succeed)
    mock_client = MagicMock()
    # Response 1: Missing XML
    # Response 2: Missing XML
    # Response 3: Good XML
    mock_client.chat.side_effect = [
        ({"content": "Fail 1"}, {}),
        ({"content": "Fail 2"}, {}),
        ({"content": "<thinking_process>Fixed</thinking_process><code_created>print('hello')</code_created>"}, {})
    ]
    # Use side_effect to return the same client every time get_client is called
    mock_context.llm_manager.get_client.side_effect = lambda role: mock_client
    
    # Mock Distiller to avoid filesystem calls
    from backend.utils.core.analysis.context_distiller import ContextDistiller
    ContextDistiller.distill_batch = MagicMock(return_value="# Distilled Context")
    
    # 3. Execute Phase
    phase = FileContentGenerationPhase(mock_context)
    # Bypass internal validation checks for the unit test
    phase._validate_file_content = MagicMock(return_value=True)
    generated_files = {}
    
    generated_files, _, _ = await phase.execute(
        project_description="Test",
        project_name="TestProj",
        project_root=Path("/tmp"),
        readme_content="Readme",
        initial_structure={},
        generated_files=generated_files,
        file_paths=[]
    )
    
    # 4. Assertions
    print(f"DEBUG: generated_files keys: {generated_files.keys()}")
    assert "test.py" in generated_files
    assert generated_files["test.py"] == "print('hello')"
    assert mock_context.file_manager.write_file.called
    # Check if move_task to 'done' was published
    mock_context.event_publisher.publish.assert_any_call(
        "agent_board_update", action="move_task", task_id="T1", new_status="done"
    )
    # Chat should have been called three times due to retries
    assert mock_client.chat.call_count == 3

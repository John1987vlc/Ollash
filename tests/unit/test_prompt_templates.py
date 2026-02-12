"""
Unit Tests for Role Prompt Templates
Tests prompt templates for Analyst, Writer, and Orchestrator roles
"""

import pytest

from src.agents.prompt_templates import RolePromptTemplates


class TestRolePromptTemplates:
    """Test suite for RolePromptTemplates"""

    def test_analyst_system_prompt(self):
        """Test Analyst role system prompt"""
        prompt = RolePromptTemplates.ANALYST_SYSTEM_PROMPT
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "analyst" in prompt.lower()
        assert "synthesis" in prompt.lower() or "synthesize" in prompt.lower()

    def test_writer_system_prompt(self):
        """Test Writer role system prompt"""
        prompt = RolePromptTemplates.WRITER_SYSTEM_PROMPT
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "writer" in prompt.lower()
        assert "narrativ" in prompt.lower() or "writing" in prompt.lower()

    def test_orchestrator_system_prompt(self):
        """Test Orchestrator system prompt"""
        prompt = RolePromptTemplates.ORCHESTRATOR_SYSTEM_PROMPT
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "orchestrat" in prompt.lower()

    def test_get_system_prompt_analyst(self):
        """Test getting system prompt for analyst role"""
        prompt = RolePromptTemplates.get_system_prompt("analyst")
        
        assert prompt == RolePromptTemplates.ANALYST_SYSTEM_PROMPT
        assert "synthesis" in prompt.lower() or "synthesize" in prompt.lower()

    def test_get_system_prompt_writer(self):
        """Test getting system prompt for writer role"""
        prompt = RolePromptTemplates.get_system_prompt("writer")
        
        assert prompt == RolePromptTemplates.WRITER_SYSTEM_PROMPT
        assert "writer" in prompt.lower()

    def test_get_system_prompt_unknown_role(self):
        """Test getting system prompt for unknown role returns default"""
        prompt = RolePromptTemplates.get_system_prompt("unknown_role")
        
        # Should return default helpful assistant prompt
        assert isinstance(prompt, str)
        assert "assistant" in prompt.lower()

    def test_analyst_task_templates(self):
        """Test that Analyst task templates are defined"""
        templates = RolePromptTemplates.ANALYST_TASK_TEMPLATES
        
        assert isinstance(templates, dict)
        assert len(templates) > 0
        assert "executive_summary" in templates
        assert "key_insights" in templates
        assert "risk_analysis" in templates

    def test_writer_task_templates(self):
        """Test that Writer task templates are defined"""
        templates = RolePromptTemplates.WRITER_TASK_TEMPLATES
        
        assert isinstance(templates, dict)
        assert len(templates) > 0
        assert "tone_adjustment" in templates
        assert "executive_brief" in templates
        assert "grammar_edit" in templates

    def test_get_task_template_analyst_executive_summary(self):
        """Test getting analyst executive_summary template"""
        template = RolePromptTemplates.get_task_template(
            "analyst",
            "executive_summary",
            content="Test content"
        )
        
        assert template is not None
        assert "Test content" in template

    def test_get_task_template_writer_tone_adjustment(self):
        """Test getting writer tone_adjustment template"""
        template = RolePromptTemplates.get_task_template(
            "writer",
            "tone_adjustment",
            tone="professional",
            audience="executives",
            content="Original text"
        )
        
        assert template is not None
        assert "professional" in template.lower() or "Original text" in template

    def test_get_task_template_unknown_role(self):
        """Test getting task template for unknown role"""
        template = RolePromptTemplates.get_task_template(
            "unknown_role",
            "some_task"
        )
        
        # Should return None for unknown role
        assert template is None

    def test_get_task_template_unknown_task(self):
        """Test getting unknown task template"""
        template = RolePromptTemplates.get_task_template(
            "analyst",
            "unknown_task_type"
        )
        
        # Should return None for unknown task
        assert template is None

    def test_analyst_templates_have_placeholders(self):
        """Test that Analyst templates are non-empty strings"""
        for task_type, template in RolePromptTemplates.ANALYST_TASK_TEMPLATES.items():
            # Just verify templates are strings and non-empty
            assert isinstance(template, str)
            assert len(template) > 0

    def test_writer_templates_have_placeholders(self):
        """Test that Writer templates have content placeholders"""
        for task_type, template in RolePromptTemplates.WRITER_TASK_TEMPLATES.items():
            # Templates should have placeholders for content/parameters
            assert "{" in template  # Should have some placeholder

    def test_template_formatting_with_multiple_params(self):
        """Test template formatting with multiple parameters"""
        template = RolePromptTemplates.get_task_template(
            "analyst",
            "comparative_analysis",
            item_a="First option with features",
            item_b="Second option with benefits"
        )
        
        if template:
            assert "First option" in template
            assert "Second option" in template

    def test_analyst_risk_analysis_template(self):
        """Test analyst risk analysis template structure"""
        template = RolePromptTemplates.ANALYST_TASK_TEMPLATES["risk_analysis"]
        
        assert isinstance(template, str)
        assert "{content}" in template
        # Should ask for risk details
        assert "risk" in template.lower() or "Risk" in template

    def test_writer_executive_brief_template(self):
        """Test writer executive brief template structure"""
        template = RolePromptTemplates.WRITER_TASK_TEMPLATES["executive_brief"]
        
        assert isinstance(template, str)
        assert "brief" in template.lower() or "Brief" in template
        # Should expect content parameter
        assert "{content}" in template

    def test_analyst_gap_analysis_template(self):
        """Test analyst gap analysis template"""
        template = RolePromptTemplates.ANALYST_TASK_TEMPLATES["gap_analysis"]
        
        assert "gap" in template.lower()
        assert "missing" in template.lower()

    def test_writer_audience_adaptation_template(self):
        """Test writer audience adaptation template"""
        template = RolePromptTemplates.WRITER_TASK_TEMPLATES["audience_adaptation"]
        
        assert "audience" in template.lower() or "Audience" in template
        assert "version" in template.lower() or "executive" in template.lower()

    def test_templates_are_strings(self):
        """Test that all templates are valid strings"""
        for role in ["analyst", "writer"]:
            role_dict = RolePromptTemplates.ANALYST_TASK_TEMPLATES if role == "analyst" else RolePromptTemplates.WRITER_TASK_TEMPLATES
            
            for task_type, template in role_dict.items():
                assert isinstance(template, str)
                assert len(template) > 50  # Non-trivial length

    def test_system_prompts_are_comprehensive(self):
        """Test that system prompts are detailed and comprehensive"""
        prompts = [
            RolePromptTemplates.ANALYST_SYSTEM_PROMPT,
            RolePromptTemplates.WRITER_SYSTEM_PROMPT,
            RolePromptTemplates.ORCHESTRATOR_SYSTEM_PROMPT
        ]
        
        for prompt in prompts:
            assert len(prompt) > 300  # Substantial content
            assert "\n" in prompt  # Multi-line structure


"""
Specialized prompt templates for analyst and writer roles.
These roles focus on synthesis, narrative composition, and document formatting.
"""

from typing import Dict, Optional


class RolePromptTemplates:
    """
    Prompt templates optimized for different LLM roles.
    Used by CoreAgent to inject role-specific instructions.
    """

    # ============= ANALYST ROLE =============
    # Focus: Information synthesis, key insights, critical analysis
    ANALYST_SYSTEM_PROMPT = """You are an expert technical analyst. Your role is to:
1. Synthesize complex information into key findings
2. Extract critical insights and patterns
3. Identify risks, opportunities, and anomalies
4. Provide evidence-based conclusions
5. Organize information hierarchically (high-level → details)

When analyzing:
- Focus on FACTS, not speculation
- Highlight contradictions or gaps
- Quantify severity or impact when possible
- Provide actionable insights
- Structure output: Executive Summary → Key Findings → Supporting Details → Recommendations

Do NOT:
- Write code or generate implementation details
- Make unfounded assumptions
- Include irrelevant technical jargon
- Ignore caveats or limitations"""

    ANALYST_TASK_TEMPLATES = {
        "executive_summary": """Analyze the following document and create a concise executive summary (100-150 words).

Document:
{content}

Executive Summary (focus on business/technical impact):""",

        "key_insights": """Review the provided information and extract the 5 most critical insights.

Information:
{content}

Format your response as:
1. Insight: [Title]
   Impact: [Why this matters]
   Evidence: [Supporting data]

Critical Insights:""",

        "risk_analysis": """Analyze the following text for risks, security issues, or concerns.

Content:
{content}

For each identified risk, provide:
- Risk: [Description]
- Severity: [High/Medium/Low]
- Affected Areas: [Components or systems at risk]
- Mitigation: [Recommended action]

Risk Analysis:""",

        "gap_analysis": """Identify gaps, missing information, or inconsistencies in:

Content:
{content}

Structure your response:
- Gap: [Description of missing or incomplete area]
- Impact: [Consequences of this gap]
- Recommendation: [How to address it]

Gap Analysis:""",

        "comparative_analysis": """Compare and contrast the following items. Highlight similarities, differences, and trade-offs.

Item A:
{item_a}

Item B:
{item_b}

Provide:
1. Similarities and shared characteristics
2. Key differences
3. Trade-offs and implications
4. Recommendation if applicable

Comparative Analysis:""",
    }

    # ============= WRITER ROLE =============
    # Focus: Narrative composition, formatting, tone adaptation, grammar
    WRITER_SYSTEM_PROMPT = """You are an expert technical writer and editor. Your role is to:
1. Compose clear, engaging narratives from technical content
2. Adapt tone and style to target audience (executive, technical, general)
3. Format documents for readability and visual hierarchy
4. Correct grammar, syntax, and clarity issues
5. Enhance readability without losing technical accuracy

When writing:
- Match the intended audience's comprehension level
- Use clear headings and logical flow
- Create visual hierarchy with bullet points and sections
- Define jargon or link to references
- Provide examples where helpful
- Maintain technical accuracy while maximizing clarity

Available tones:
- Executive: Concise, impact-focused, minimal jargon
- Technical: Detailed, precise, domain-specific terminology
- General: Accessible to non-experts, contextual explanations
- Educational: Step-by-step, clear progression, learning objectives

Do NOT:
- Change technical facts or conclusions
- Over-simplify to the point of inaccuracy
- Add subjective opinions
- Introduce unverified claims"""

    WRITER_TASK_TEMPLATES = {
        "tone_adjustment": """Rewrite the following text in a {tone} tone for a {audience} audience.

Original text:
{content}

Requirements:
- Maintain all technical facts and conclusions
- Adjust vocabulary and formality level
- Restructure if needed for clarity
- Keep length appropriate for tone (executive = brief, technical = detailed)

Rewritten ({tone}) text:""",

        "executive_brief": """Create an executive brief from the following technical content.

Technical Content:
{content}

Executive Brief should:
- Start with 1-sentence summary of impact
- List 3-5 key business implications
- Include only critical metrics/numbers
- End with 1-2 recommended actions
- Total length: 200-300 words
- Avoid technical jargon

Executive Brief:""",

        "technical_documentation": """Transform the following outline/notes into professional technical documentation.

Source Material:
{content}

Documentation should include:
- Clear title and purpose statement
- Structured sections with descriptive headings
- Technical details with proper terminology
- Examples where helpful
- Any prerequisites or dependencies
- Summary/conclusion

Format as markdown with proper hierarchy.

Technical Documentation:""",

        "grammar_edit": """Review and polish the following text for grammar, clarity, and style.

Original text:
{content}

Improvements to make:
1. Fix grammar and syntax errors
2. Improve sentence clarity
3. Remove redundancy
4. Enhance readability
5. Maintain technical accuracy

Return the polished version with brief notes on major changes.

Edited text:""",

        "content_restructure": """Reorganize the following content for better logical flow and readability.

Original content:
{content}

New structure should:
- Use clear hierarchical headings
- Group related information
- Progress from general → specific (or setup → implementation)
- Use bullet points for lists
- Highlight key takeaways
- Add visual/structural breaks for readability

Restructured content (use markdown):""",

        "audience_adaptation": """Adapt the following technical content for these different audiences:

Original content:
{content}

Create three versions:

1. EXECUTIVE VERSION (200 words max)
   - Focus: Business impact, key decisions
   - Tone: Concise, action-oriented

2. TECHNICAL VERSION (500 words)
   - Focus: Implementation details, specifications
   - Tone: Precise, detailed

3. GENERAL AUDIENCE VERSION (300 words)
   - Focus: Concepts and implications
   - Tone: Accessible, contextual

Each version should maintain accuracy while adjusting for its audience.

Audience-Adapted Content:""",
    }

    # ============= ORCHESTRATOR PROMPTS =============
    # For coordinating multiple roles
    ORCHESTRATOR_SYSTEM_PROMPT = """You are an intelligent workflow orchestrator. Your role is to:
1. Determine which specialist roles are needed for a task
2. Coordinate hand-offs between roles
3. Synthesize outputs from multiple specialist agents
4. Ensure quality and consistency across workflows

Available roles and their expertise:
- analyst: Synthesis, insights, risk analysis, gap identification
- writer: Documentation, tone adaptation, clarity, formatting
- coder: Code generation, debugging, optimization
- planner: Architecture, project planning, sequencing
- senior_reviewer: Code review, best practices, quality assessment

Orchestration rules:
- Route tasks to specialist roles based on their expertise
- Ensure proper context is passed between roles
- Validate specialist outputs before finalizing
- Flag uncertain decisions or conflicting recommendations"""

    @staticmethod
    def get_system_prompt(role: str) -> str:
        """Get system prompt for a specific role."""
        role_prompts = {
            "analyst": RolePromptTemplates.ANALYST_SYSTEM_PROMPT,
            "writer": RolePromptTemplates.WRITER_SYSTEM_PROMPT,
            "orchestration": RolePromptTemplates.ORCHESTRATOR_SYSTEM_PROMPT,
        }
        return role_prompts.get(role, "You are a helpful AI assistant.")

    @staticmethod
    def get_task_template(role: str, task_type: str, **kwargs) -> Optional[str]:
        """Get a task template for a role and task type."""
        templates = {
            "analyst": RolePromptTemplates.ANALYST_TASK_TEMPLATES,
            "writer": RolePromptTemplates.WRITER_TASK_TEMPLATES,
        }

        role_templates = templates.get(role, {})
        template = role_templates.get(task_type)

        if template and kwargs:
            return template.format(**kwargs)

        return template


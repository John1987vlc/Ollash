import json
import re # Import re for regex parsing
from typing import Dict, List, Tuple


def _format_related_files(related_files: Dict[str, str]) -> str:
    """Format related files context for prompts."""
    if not related_files:
        return ""
    context = "\nAlready generated files:\n"
    for path in related_files:
        context += f"- {path}\n"
    return context


class AutoGenPrompts:
    """Centralized prompt templates for the auto-generation pipeline.

    All prompts instruct models to output RAW file content without markdown fences.
    """

    @staticmethod
    def _extract_tech_stack_details(readme_content: str) -> Dict[str, Dict[str, str]]:
        """
        Extracts frontend and backend technology stacks from the README content.
        Assumes markdown tables under specific headings.
        """
        tech_stacks = {"frontend": {}, "backend": {}}

        # Regex to find technology stack sections
        frontend_match = re.search(
            r"### \*\*🌐 Frontend\*\*\s*\| Technology \| Purpose \| Version \|\s*\|-+\|-+\|-+\|\s*(.*?)(?=\n###|\Z)",
            readme_content,
            re.DOTALL,
        )
        backend_match = re.search(
            r"### \*\*🏗️ Backend\*\*\s*\| Technology \| Purpose \| Version \|\s*\|-+\|-+\|-+\|\s*(.*?)(?=\n###|\Z)",
            readme_content,
            re.DOTALL,
        )

        if frontend_match:
            lines = frontend_match.group(1).strip().split("\n")
            for line in lines:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    tech = parts[0].replace('**', '').strip().lower()
                    version = parts[2].strip().replace('v', '') # Remove 'v' prefix
                    tech_stacks["frontend"][tech] = version

        if backend_match:
            lines = backend_match.group(1).strip().split("\n")
            for line in lines:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 3:
                    tech = parts[0].replace('**', '').strip().lower()
                    version = parts[2].strip().replace('v', '') # Remove 'v' prefix
                    tech_stacks["backend"][tech] = version

        return tech_stacks

    @staticmethod
    def readme_generation(project_description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1."""
        system = (
            "You are a senior software architect. "
            "Create comprehensive, detailed technical documentation."
        )
        user = (
            "Create a comprehensive and detailed README.md for the following project. "
            "The README should include:\n"
            "- Project title and description\n"
            "- Main features and functionality\n"
            "- Technology stack\n"
            "- Project structure overview\n"
            "- Installation and setup instructions\n"
            "- Usage examples\n\n"
            "Be thorough and specific. This README will be used to generate the "
            "entire project structure.\n\n"
            f"Project Description: {project_description}"
        )
        return system, user

    @staticmethod
    def structure_generation(readme_content: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 2."""
        # Extract Project Structure section from README if it exists
        project_structure_section_match = re.search(
            r"## \*\*📂 Project Structure\*\*(.*?)(?=\n##|\Z)",
            readme_content,
            re.DOTALL,
        )
        project_structure_hint = ""
        if project_structure_section_match:
            project_structure_hint = (
                "\n\nHere is a suggested 'Project Structure' section from the README "
                "to guide your JSON output:\n"
                f"{project_structure_section_match.group(1).strip()}\n"
            )

        system = (
            "You are an expert at designing comprehensive project file structures. "
            "Your task: given a project README.md, output a single JSON object "
            "representing the COMPLETE and DETAILED project file structure that "
            "fully reflects the described project, including its frontend, backend, "
            "and any other specified components.\n\n"
            "The JSON format must follow this structure exactly:\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            "    {\n"
            '      "name": "folder-name",\n'
            '      "folders": [],\n'
            '      "files": ["file1.ext", "file2.ext"]\n'
            "    }\n"
            "  ],\n"
            '  "files": ["rootfile.ext"]\n'
            "}\n\n"
            "Rules:\n"
            "- Infer the structure strictly from the README.md, prioritizing any "
            "explicit 'Project Structure' section if present.\n"
            "- Create a comprehensive structure, including all major components (e.g., frontend, backend apps, shared packages) "
            "and essential configuration/source files.\n"
            "- Do not invent features not described in the README.\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- Complete the ENTIRE JSON structure. Do not truncate.\n"
            "- Include common and expected files for the described technologies (e.g., package.json, next.config.js, tsconfig.json for Next.js; main.ts, module.ts for NestJS).\n"
            "- The structure should be logical and follow best practices for the specified tech stack."
        )
        user = (
            "Based on the following README.md, generate the COMPLETE and DETAILED "
            "JSON project structure.\n\n"
            f"Project README:\n{readme_content}\n"
            f"{project_structure_hint}\n\n"
            "Remember: Output ONLY the complete JSON, nothing else."
        )
        return system, user

    @staticmethod
    def file_content_generation(
        file_path: str,
        readme_content: str,
        json_structure: dict,
        related_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 4.

        Instructs model to output raw file content without markdown.
        """
        system = (
            f"You are generating the file: {file_path}\n"
            "Output ONLY the raw file content. "
            "Do NOT use markdown code blocks or ``` fences. "
            "Do NOT include any explanation before or after the content. "
            "Start directly with the first line of the file."
        )
        user = (
            f"Generate the COMPLETE content for: {file_path}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Project Structure:\n{json.dumps(json_structure, indent=2)}\n"
            f"{_format_related_files(related_files)}\n"
            "Requirements:\n"
            "- Output ONLY the raw file content, nothing else\n"
            "- Do NOT wrap in markdown code blocks\n"
            "- Include necessary imports, comments, and documentation\n"
            "- If it's a config file, provide appropriate configuration\n"
            "- If it's a Python __init__.py, provide proper imports\n"
            "- The file must be complete and syntactically correct\n"
        )
        return system, user

    @staticmethod
    def package_json_generation(
        file_path: str,
        tech_stack_details: Dict[str, Dict[str, str]],
        app_type: str, # 'frontend' or 'backend'
        json_structure: dict,
        related_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for package.json generation."""
        # Normalize app_type for display
        display_app_type = app_type.capitalize()

        # Extract relevant tech stack for this app_type
        relevant_tech = tech_stack_details.get(app_type, {})
        tech_list = "\n".join(
            [f"- {tech.capitalize()}: {version}" for tech, version in relevant_tech.items()]
        ) or "No specific technologies listed."

        system = (
            f"You are generating the {display_app_type} package.json file: {file_path}\n"
            "Output ONLY the raw JSON content for the package.json file. "
            "Do NOT use markdown code blocks or ``` fences. "
            "Do NOT include any explanation before or after the content. "
            "Start directly with the opening curly brace '{'."
        )

        user = (
            f"Generate the COMPLETE and syntactically correct package.json content for the "
            f"{display_app_type} application.\n\n"
            f"File to generate: {file_path}\n\n"
            f"{display_app_type} Technology Stack identified from README:\n"
            f"{tech_list}\n\n"
            f"Project Structure (relevant excerpt):\n{json.dumps(json_structure, indent=2)}\n"
            f"{_format_related_files(related_files)}\n\n"
            "Requirements:\n"
            "- Include `name`, `version` (use '0.1.0'), and `private: true`.\n"
            "- Populate `dependencies` with the exact technologies and versions from the Technology Stack above.\n"
            "- For a Frontend (Next.js/React/TypeScript) project, include standard `scripts` "
            "like `dev`, `build`, `start`, `lint` and common `devDependencies` (e.g., eslint, postcss, autoprefixer).\n"
            "- For a Backend (NestJS/Node.js/Express) project, include standard `scripts` "
            "like `build`, `format`, `start`, `start:dev`, `start:prod`, `lint`, `test` and common `devDependencies` "
            "(e.g., @nestjs/cli, @types/node, typescript, jest).\n"
            "- Ensure all versions are valid and correctly formatted for npm.\n"
            "- Output ONLY valid JSON, nothing else."
        )
        return system, user

    @staticmethod
    def file_refinement(
        file_path: str, current_content: str, readme_excerpt: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 5."""
        system = (
            f"You are refining: {file_path}\n"
            "Output ONLY the improved raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"Improve the following file: {file_path}\n\n"
            f"Current content:\n{current_content}\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Tasks:\n"
            "- Add error handling where appropriate\n"
            "- Improve code quality and efficiency\n"
            "- Add missing documentation\n"
            "- Fix any obvious bugs or issues\n"
            "- Keep existing functionality intact\n\n"
            "Output ONLY the complete improved file content. "
            "No markdown code blocks. No explanation."
        )
        return system, user

    @staticmethod
    def file_fix(
        file_path: str, current_content: str, validation_error: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for verification-fix loop."""
        system = (
            f"You are fixing the file: {file_path}\n"
            "Output ONLY the corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"The following file failed validation. Fix it and output the COMPLETE "
            f"corrected file.\n\n"
            f"File: {file_path}\n\n"
            f"Validation error: {validation_error}\n\n"
            f"Current content:\n{current_content}\n\n"
            "Output ONLY the corrected raw file content. "
            "No markdown. No explanation."
        )
        return system, user

    @staticmethod
    def project_review(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 6."""
        system = "You are conducting a final project review."
        user = (
            f"Review the following project and provide a brief assessment:\n\n"
            f"{project_summary}\n\n"
            "Provide:\n"
            "1. Overall quality assessment (1-10)\n"
            "2. Key strengths\n"
            "3. Potential improvements\n"
            "4. Any critical issues to address\n\n"
            "Keep your response concise and actionable."
        )
        return system, user
    
    @staticmethod
    def suggest_improvements_prompt(
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        loop_num: int,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for suggesting improvements."""
        system = (
            "You are an AI assistant specialized in software architecture and code quality. "
            "Your task is to analyze a partially generated software project and suggest "
            "concrete improvements to make it more complete, functional, and adhere to best practices."
        )
        user = (
            f"Analyze the following project at its current state (Iteration {loop_num}). "
            "Identify 3-5 concrete, actionable improvements that would significantly enhance the project's "
            "completeness, functionality, or code quality, based on the initial project description and README.\n\n"
            "Consider aspects like:\n"
            "- Missing core functionalities or features mentioned in the README.\n"
            "- Incomplete configuration files (e.g., missing scripts, dependencies in package.json).\n"
            "- Basic file structures that need further detail.\n"
            "- Best practices for the technologies used.\n\n"
            "Project Description: {project_description}\n\n"
            "Project README:\n{readme_content}\n\n"
            "Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            "Currently generated files (first 500 chars of each):\n"
        )
        for path, content in list(current_files.items())[:5]: # Provide context for a few files
            user += f"--- File: {path} ---\n{content[:500]}...\n\n"
        
        user += (
            "Output your suggestions as a markdown bullet list. Each suggestion should be concise "
            "and clearly state what needs to be improved."
        )
        return system, user

    @staticmethod
    def generate_improvement_plan_prompt(
        suggestions: List[str],
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for generating an improvement plan."""
        system = (
            "You are an AI project manager and architect. "
            "Your task is to create a detailed, step-by-step plan to implement "
            "a set of suggested improvements for a software project. "
            "The plan should be in JSON format and describe concrete actions."
        )
        user = (
            "Based on the following project context and suggested improvements, "
            "create a detailed action plan in JSON format. "
            "The plan should prioritize actions and describe how to achieve each suggestion.\n\n"
            "Suggested Improvements:\n"
            f"{'\\n'.join([f'- {s}' for s in suggestions])}\n\n"
            "Project Description: {project_description}\n\n"
            "Project README:\n{readme_content}\n\n"
            "Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            "Currently generated files (first 500 chars of each):\n"
        )
        for path, content in list(current_files.items())[:5]: # Provide context for a few files
            user += f"--- File: {path} ---\n{content[:500]}...\n\n"

        user += (
            "The JSON plan should be a single object with an 'actions' key, "
            "which is a list of action objects. Each action object must have:\n"
            "- 'type': 'create_file', 'modify_file', 'create_folder', 'delete_file'\n"
            "- 'path': (string) The relative path to the file/folder. Required for 'create_file', 'modify_file', 'delete_file'.\n"
            "- 'target_folder': (string) The relative path to the folder. Required for 'create_folder'.\n"
            "- 'description': (string) A brief explanation of the action.\n"
            "- 'content': (string, optional) The full content for 'create_file' or 'modify_file' if the content is small and deterministic. "
            "Otherwise, leave empty for LLM to generate dynamically.\n\n"
            "Example Plan Structure:\n"
            "{\n"
            "  \"actions\": [\n"
            "    {\"type\": \"create_file\", \"path\": \"src/features/auth/Login.js\", \"description\": \"Add a login component.\", \"content\": \"// Login component code...\"},\n"
            "    {\"type\": \"modify_file\", \"path\": \"src/App.js\", \"description\": \"Integrate login component.\"},\n"
            "    {\"type\": \"create_folder\", \"target_folder\": \"src/config\", \"description\": \"Create config directory.\"}\n"
            "  ]\n"
            "}\n"
            "Output ONLY the JSON plan, nothing else."
        )
        return system, user

    @staticmethod
    def senior_review_prompt(
        project_description: str,
        project_name: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        review_attempt: int,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a senior-level project review."""
        system = (
            "You are a highly experienced Senior Software Architect and Lead Developer. "
            "Your task is to perform a rigorous, critical review of a software project. "
            "Your assessment should ensure the project is correct, complete, logical, "
            "adheres to best practices, and fully addresses the initial description.\n"
            "Provide your review in JSON format, indicating overall status and specific issues."
        )
        user = (
            f"Perform a comprehensive review of the project '{project_name}' (Review Attempt {review_attempt}).\n\n"
            "Project Description: {project_description}\n\n"
            "Project README:\n{readme_content}\n\n"
            "Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            "All currently generated files (first 500 chars of each):\n"
        )
        for path, content in current_files.items(): # Provide context for all files for senior review
            user += f"--- File: {path} ---\n{content[:500]}...\n\n"

        user += (
            "Provide your review in JSON format with the following keys:\n"
            "- 'status': (string) 'passed' if the project is complete and satisfactory, 'failed' otherwise.\n"
            "- 'summary': (string) A concise overall assessment of the project.\n"
            "- 'issues': (list of objects) A list of specific, actionable issues if the status is 'failed'. "
            "Each issue object must have:\n"
            "  - 'description': (string) Detail the problem.\n"
            "  - 'severity': (string) 'critical', 'major', 'minor'.\n"
            "  - 'recommendation': (string) Suggest a concrete solution.\n"
            "  - 'file': (string, optional) The relative path to the file most relevant to the issue.\n\n"
            "If the project 'passed', the 'issues' list should be empty.\n"
            "Output ONLY the JSON, nothing else."
        )
        return system, user
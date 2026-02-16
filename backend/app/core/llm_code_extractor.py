"""
LLM-assisted Code Extractor: Intelligent code extraction and organization.

Uses LLM to:
- Extract code blocks even without standard markdown format
- Infer project structure and folder organization
- Suggest meaningful filenames based on code purpose
- Group related code into appropriate files
- Generate accurate dependency lists
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.schemas.onboarding import ChatMessage


@dataclass
class SmartExtractedCode:
    """Enhanced code extraction result with LLM-inferred metadata."""
    filename: str  # Full path with folder structure
    language: str
    content: str
    description: str  # LLM-generated description of what this code does
    dependencies: List[str]  # Required packages/modules
    source_agent: Optional[str] = None
    related_files: List[str] = None  # Files that this code depends on or relates to

    def __post_init__(self):
        if self.related_files is None:
            self.related_files = []


@dataclass
class ProjectStructure:
    """LLM-inferred project organization."""
    project_type: str  # e.g., "web_app", "data_science", "ml_pipeline", "cli_tool"
    suggested_folders: List[str]  # e.g., ["src", "tests", "config", "data"]
    entry_point: Optional[str]  # Main file to run, e.g., "src/main.py"
    readme_content: Optional[str]  # LLM-generated README


class LLMCodeExtractor:
    """Intelligent code extractor using LLM assistance."""

    def __init__(
        self,
        llm_call: Optional[Callable[[str, List[ChatMessage]], str]] = None,
    ):
        """Initialize the LLM code extractor.

        Args:
            llm_call: Sync callable (system_prompt, messages) -> str. Uses stored API keys when
                      invoked from API via resolve_llm_call(db). Required for production.
        """
        self.llm_call = llm_call

    async def analyze_project_structure(
        self,
        messages: List[Dict[str, Any]],
    ) -> ProjectStructure:
        """Analyze meeting messages to infer project type and structure.

        Args:
            messages: Meeting messages with agent discussions.

        Returns:
            ProjectStructure with inferred organization.
        """
        # Build context from meeting messages
        context = self._build_context(messages)

        # Prompt LLM to analyze project structure
        prompt = f"""Analyze this research/development meeting transcript and infer the project structure.

Meeting transcript:
{context}

Respond with a JSON object containing:
{{
  "project_type": "web_app|data_science|ml_pipeline|cli_tool|library|research_code|other",
  "suggested_folders": ["folder1", "folder2", ...],
  "entry_point": "path/to/main_file.ext or null",
  "readme_content": "Brief README.md content explaining the project"
}}

Consider:
- What type of project is being discussed?
- What folder structure makes sense for this project type?
- What would be the main entry point?
- Include standard folders like tests/, docs/ if appropriate

Respond ONLY with valid JSON, no markdown formatting."""

        llm_messages = [ChatMessage(role="user", content=prompt)]

        # Call LLM (sync llm_call run in executor)
        if not self.llm_call:
            raise RuntimeError("LLM callable required. Pass resolve_llm_call(db) from the API.")
        content = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.llm_call("", llm_messages)
        )

        # Parse response
        try:
            data = json.loads(content.strip())
            return ProjectStructure(
                project_type=data.get("project_type", "other"),
                suggested_folders=data.get("suggested_folders", []),
                entry_point=data.get("entry_point"),
                readme_content=data.get("readme_content"),
            )
        except json.JSONDecodeError:
            # Fallback to basic structure
            return ProjectStructure(
                project_type="other",
                suggested_folders=["src", "tests"],
                entry_point=None,
                readme_content=None,
            )

    async def extract_code_smart(
        self,
        messages: List[Dict[str, Any]],
        project_structure: Optional[ProjectStructure] = None,
    ) -> List[SmartExtractedCode]:
        """Extract and organize code using LLM intelligence.

        Args:
            messages: Meeting messages containing code and discussions.
            project_structure: Optional pre-analyzed project structure.

        Returns:
            List of SmartExtractedCode with organized files and paths.
        """
        # Analyze project structure first if not provided
        if not project_structure:
            project_structure = await self.analyze_project_structure(messages)

        # Build full context
        context = self._build_context(messages)

        # Prompt LLM to extract and organize code
        prompt = f"""Extract all code from this meeting transcript and organize it into a well-structured project.

Meeting transcript:
{context}

Project type: {project_structure.project_type}
Suggested folder structure: {', '.join(project_structure.suggested_folders)}

Your task:
1. Find ALL code snippets (even if not in markdown code blocks)
2. Organize code into appropriate files with meaningful names
3. Group related code together
4. Use the suggested folder structure
5. Detect the programming language for each file
6. List dependencies/imports for each file
7. Provide a brief description of what each file does

Respond with a JSON array of code files:
[
  {{
    "filename": "path/to/file.ext",
    "language": "python|javascript|...",
    "content": "the actual code content",
    "description": "what this file does",
    "dependencies": ["package1", "package2"],
    "related_files": ["other/file.py"]
  }},
  ...
]

Important:
- Use proper file paths with folders (e.g., "src/models/pipeline.py", not just "pipeline.py")
- Merge related code snippets into single files when appropriate
- Include test files if test code is mentioned
- Include config files if configurations are discussed
- Only include actual CODE, not explanatory text
- If no code exists, return []

Respond ONLY with valid JSON array, no markdown formatting."""

        llm_messages = [ChatMessage(role="user", content=prompt)]

        # Call LLM (sync llm_call run in executor)
        if not self.llm_call:
            raise RuntimeError("LLM callable required. Pass resolve_llm_call(db) from the API.")
        content = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.llm_call("", llm_messages)
        )

        # Parse response
        try:
            data = json.loads(content.strip())
            results = []
            for item in data:
                # Find source agent if possible
                source_agent = self._find_source_agent(item["content"], messages)

                results.append(SmartExtractedCode(
                    filename=item["filename"],
                    language=item.get("language", "text"),
                    content=item["content"],
                    description=item.get("description", ""),
                    dependencies=item.get("dependencies", []),
                    source_agent=source_agent,
                    related_files=item.get("related_files", []),
                ))
            return results
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback: use basic extraction
            print(f"LLM extraction failed: {e}, falling back to regex extraction")
            return []

    async def generate_smart_requirements(
        self,
        code_files: List[SmartExtractedCode],
    ) -> str:
        """Generate requirements.txt using LLM to ensure all dependencies are captured.

        Args:
            code_files: Extracted code files with dependencies.

        Returns:
            requirements.txt content.
        """
        # Collect all code content
        all_code = "\n\n".join([
            f"# {file.filename}\n{file.content}"
            for file in code_files
            if file.language in ("python", "py")
        ])

        if not all_code:
            return ""

        # Collect dependencies mentioned by LLM
        mentioned_deps = set()
        for file in code_files:
            mentioned_deps.update(file.dependencies)

        # Prompt LLM to analyze imports
        prompt = f"""Analyze this Python code and generate a complete requirements.txt file.

Code:
{all_code}

Dependencies already identified: {', '.join(mentioned_deps) if mentioned_deps else 'none'}

Your task:
1. Find ALL import statements
2. Exclude standard library modules (os, sys, json, etc.)
3. Map imports to PyPI package names (e.g., 'sklearn' → 'scikit-learn')
4. Include version constraints if specific versions are mentioned in comments
5. Return ONLY the package list, one per line

Format:
package1
package2==1.2.3
package3>=2.0.0

Respond ONLY with the requirements list, no explanations or markdown."""

        llm_messages = [ChatMessage(role="user", content=prompt)]

        # Call LLM (sync llm_call run in executor)
        if not self.llm_call:
            raise RuntimeError("LLM callable required. Pass resolve_llm_call(db) from the API.")
        content = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.llm_call("", llm_messages)
        )

        # Return cleaned response
        requirements = content.strip()
        # Remove any markdown code blocks if present
        requirements = requirements.replace("```", "").strip()
        return requirements

    def _build_context(self, messages: List[Dict[str, Any]]) -> str:
        """Build a readable context string from meeting messages."""
        lines = []
        for msg in messages:
            role = msg.get("role", "assistant")
            agent_name = msg.get("agent_name", "User")
            content = msg.get("content", "")

            if role == "user":
                lines.append(f"[User]: {content}")
            else:
                lines.append(f"[{agent_name}]: {content}")

        return "\n\n".join(lines)

    def _find_source_agent(self, code_content: str, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Try to find which agent generated this code."""
        # Simple heuristic: find message containing the code
        for msg in messages:
            if msg.get("content") and code_content[:50] in msg["content"]:
                return msg.get("agent_name")
        return None


async def extract_with_llm(
    messages: List[Dict[str, Any]],
    llm_call: Callable[[str, List[ChatMessage]], str],
) -> tuple[List[SmartExtractedCode], ProjectStructure]:
    """Convenience function for LLM-assisted extraction.

    Args:
        messages: Meeting messages.
        llm_call: Sync callable (system_prompt, messages) -> str (e.g. resolve_llm_call(db)).

    Returns:
        Tuple of (extracted code files, project structure).
    """
    extractor = LLMCodeExtractor(llm_call=llm_call)
    structure = await extractor.analyze_project_structure(messages)
    code_files = await extractor.extract_code_smart(messages, structure)
    return code_files, structure

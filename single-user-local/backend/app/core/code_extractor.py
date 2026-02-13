"""
CodeExtractor: Extracts code blocks from meeting messages.

Parses markdown-style code fences (```language ... ```) from agent responses
and creates structured code artifacts.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExtractedCode:
    """A code block extracted from a message."""
    language: str
    content: str
    source_agent: Optional[str]
    suggested_filename: str


# Language → file extension mapping
LANG_EXTENSIONS = {
    "python": ".py",
    "py": ".py",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "java": ".java",
    "cpp": ".cpp",
    "c++": ".cpp",
    "c": ".c",
    "go": ".go",
    "rust": ".rs",
    "ruby": ".rb",
    "bash": ".sh",
    "shell": ".sh",
    "sh": ".sh",
    "sql": ".sql",
    "html": ".html",
    "css": ".css",
    "json": ".json",
    "yaml": ".yaml",
    "yml": ".yaml",
    "markdown": ".md",
    "r": ".R",
}

# Pattern to match fenced code blocks: ```lang\ncode\n```
CODE_BLOCK_PATTERN = re.compile(
    r"```(\w+)?\s*\n(.*?)```",
    re.DOTALL,
)


def extract_code_blocks(
    text: str,
    source_agent: Optional[str] = None,
) -> List[ExtractedCode]:
    """Extract all code blocks from a text string.

    Parses markdown-style fenced code blocks (```language ... ```).

    Args:
        text: The text to extract code from.
        source_agent: Optional agent name for attribution.

    Returns:
        List of ExtractedCode objects.
    """
    blocks = []
    for i, match in enumerate(CODE_BLOCK_PATTERN.finditer(text)):
        language = (match.group(1) or "text").lower()
        content = match.group(2).strip()

        if not content:
            continue

        ext = LANG_EXTENSIONS.get(language, ".txt")
        filename = _suggest_filename(content, language, ext, i)

        blocks.append(ExtractedCode(
            language=language,
            content=content,
            source_agent=source_agent,
            suggested_filename=filename,
        ))

    return blocks


def _suggest_filename(
    content: str,
    language: str,
    ext: str,
    index: int,
) -> str:
    """Try to infer a filename from the code content."""
    # Python: look for class or def at top level
    if language in ("python", "py"):
        class_match = re.search(r"^class\s+(\w+)", content, re.MULTILINE)
        if class_match:
            return _to_snake_case(class_match.group(1)) + ext
        func_match = re.search(r"^def\s+(\w+)", content, re.MULTILINE)
        if func_match:
            return func_match.group(1) + ext

    # JavaScript/TypeScript: look for export default or function
    if language in ("javascript", "js", "typescript", "ts"):
        export_match = re.search(r"export\s+(?:default\s+)?(?:class|function)\s+(\w+)", content)
        if export_match:
            return export_match.group(1) + ext

    # Fallback: code_N.ext
    return f"code_{index + 1}{ext}"


def _to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result = re.sub(r"([A-Z])", r"_\1", name).lower().lstrip("_")
    return result


def extract_from_meeting_messages(
    messages: List[dict],
) -> List[ExtractedCode]:
    """Extract code blocks from a list of meeting messages.

    Args:
        messages: List of dicts with 'content', 'agent_name', 'role' keys.

    Returns:
        All code blocks found across all messages.
    """
    all_blocks = []
    for msg in messages:
        blocks = extract_code_blocks(
            msg["content"],
            source_agent=msg.get("agent_name"),
        )
        all_blocks.extend(blocks)
    return all_blocks

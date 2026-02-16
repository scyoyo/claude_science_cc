"""
CodeExtractor: Extracts code blocks from meeting messages.

Parses:
1. Markdown-style code fences (```language ... ```) from agent responses
2. JSON format from agent outputs: [{"path": "...", "language": "...", "code": "..."}]
"""

import json
import re
from dataclasses import dataclass
from typing import List, Optional, Set


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

# Pattern to find path-like filenames in transcript (e.g. src/main.py, lib/utils.py)
# Matches: word chars, slashes, then filename with extension
PATH_IN_TEXT_PATTERN = re.compile(
    r"(?:^|[\s,，、:(\[\])\n])((?:[\w.-]+/)+[\w.-]+\.\w+)(?=[\s,\)\]}\n.]|$)"
)

# Patterns to detect filepath hints in text before a code block
FILEPATH_PATTERNS = [
    # # filename: path/to/file.py  or  # Filename: path/to/file.py
    re.compile(r"#\s*[Ff]ilename:\s*`?([^\s`]+)`?"),
    # Save as `path/to/file.py`  or  Save to `path/to/file.py`
    re.compile(r"[Ss]ave\s+(?:as|to)\s+`([^`]+)`"),
    # File: `path/to/file.py`  or  File: path/to/file.py
    re.compile(r"[Ff]ile:\s*`?([^\s`]+\.\w+)`?"),
    # ### path/to/file.py  (heading followed by a path-like string)
    re.compile(r"###\s+(`?([^\s`]+\.\w+)`?)"),
    # **path/to/file.py**
    re.compile(r"\*\*([^\s*]+\.\w+)\*\*"),
]

# Known stdlib modules that should NOT appear in requirements.txt
PYTHON_STDLIB = {
    "os", "sys", "re", "json", "math", "random", "datetime", "time",
    "collections", "itertools", "functools", "typing", "pathlib",
    "io", "csv", "copy", "hashlib", "base64", "uuid", "logging",
    "argparse", "unittest", "dataclasses", "abc", "enum", "string",
    "textwrap", "struct", "operator", "contextlib", "warnings",
    "subprocess", "shutil", "tempfile", "glob", "fnmatch",
    "stat", "fileinput", "pprint", "dis", "inspect", "traceback",
    "pickle", "shelve", "sqlite3", "gzip", "zipfile", "tarfile",
    "socket", "http", "urllib", "email", "html", "xml",
    "threading", "multiprocessing", "concurrent", "asyncio",
    "signal", "queue", "heapq", "bisect", "array", "weakref",
    "types", "codecs", "unicodedata", "locale", "gettext",
    "platform", "ctypes", "decimal", "fractions", "statistics",
    "secrets", "hmac",
}

# Common import → PyPI package name mapping
IMPORT_TO_PACKAGE = {
    "numpy": "numpy",
    "np": "numpy",
    "pandas": "pandas",
    "pd": "pandas",
    "sklearn": "scikit-learn",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "plt": "matplotlib",
    "seaborn": "seaborn",
    "sns": "seaborn",
    "torch": "torch",
    "torchvision": "torchvision",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "keras": "keras",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "flask": "Flask",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "requests": "requests",
    "httpx": "httpx",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "celery": "celery",
    "redis": "redis",
    "boto3": "boto3",
    "botocore": "botocore",
    "jwt": "PyJWT",
    "cryptography": "cryptography",
    "paramiko": "paramiko",
    "tqdm": "tqdm",
    "click": "click",
    "typer": "typer",
    "rich": "rich",
    "pytest": "pytest",
    "transformers": "transformers",
    "datasets": "datasets",
    "tokenizers": "tokenizers",
    "openai": "openai",
    "anthropic": "anthropic",
    "langchain": "langchain",
    "streamlit": "streamlit",
    "gradio": "gradio",
    "plotly": "plotly",
    "networkx": "networkx",
    "sympy": "sympy",
    "biopython": "biopython",
    "Bio": "biopython",
    "rdkit": "rdkit",
}


def _collect_path_candidates_from_text(text: str) -> List[str]:
    """Collect path-like filenames (e.g. src/main.py) from text in order. Used for transcript-wide hints."""
    candidates: List[str] = []
    for m in PATH_IN_TEXT_PATTERN.finditer(text):
        path = m.group(1).strip()
        if path and "." in path.split("/")[-1] and path not in candidates:
            candidates.append(path)
    return candidates


def _detect_filepath_hint(text_before_block: str) -> Optional[str]:
    """Search text preceding a code block for filepath hints.

    Looks for patterns like:
    - # filename: path/to/file.py
    - Save as `path/to/file.py`
    - File: `path/to/file.py`
    - ### path/to/file.py
    - **path/to/file.py**

    Returns the detected filepath or None.
    """
    # Only look at the last few lines before the code block
    lines = text_before_block.strip().split("\n")
    search_text = "\n".join(lines[-5:])

    for pattern in FILEPATH_PATTERNS:
        match = pattern.search(search_text)
        if match:
            # Use the last group that is not None (some patterns have multiple groups)
            filepath = match.group(match.lastindex or 1)
            # Clean up: remove backticks, leading/trailing whitespace
            filepath = filepath.strip("`").strip()
            # Basic validation: must have an extension
            if "." in filepath.split("/")[-1]:
                return filepath
    return None


def _extract_json_code_blocks(
    text: str,
    source_agent: Optional[str] = None,
) -> List[ExtractedCode]:
    """Extract code from JSON format: [{"path": "...", "language": "...", "code": "..."}].

    Agents may output this format when instructed. Handles both raw JSON and
    JSON inside ```json ... ``` fences.
    """
    results = []
    # Try JSON array pattern (possibly inside markdown fence)
    json_pattern = re.compile(
        r'\[\s*\{[^\[\]]*"path"[^\[\]]*"language"[^\[\]]*"code"[^\[\]]*\}[\s,]*\{[^\[\]]*\}[^\]]*\]',
        re.DOTALL,
    )
    # Simpler: find ```json ... ``` or raw [...]
    for fence_match in re.finditer(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL):
        block = fence_match.group(1).strip()
        try:
            data = json.loads(block)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "path" in item and "code" in item:
                        path = str(item["path"]).strip()
                        lang = str(item.get("language", "python")).lower()
                        code = str(item["code"]).strip()
                        if path and code:
                            ext = LANG_EXTENSIONS.get(lang, ".txt")
                            if "." not in path.split("/")[-1]:
                                path = path.rstrip("/") + ext
                            results.append(ExtractedCode(
                                language=lang,
                                content=code,
                                source_agent=source_agent,
                                suggested_filename=path,
                            ))
        except json.JSONDecodeError:
            pass
    # Also try raw JSON array in text (no fence)
    brace_match = re.search(r'\[\s*\{[^\]]*"path"[^\]]*"code"[^\]]*\}[^\]]*\]', text, re.DOTALL)
    if brace_match and not results:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "path" in item and "code" in item:
                        path = str(item["path"]).strip()
                        lang = str(item.get("language", "python")).lower()
                        code = str(item["code"]).strip()
                        if path and code:
                            ext = LANG_EXTENSIONS.get(lang, ".txt")
                            if "." not in path.split("/")[-1]:
                                path = path.rstrip("/") + ext
                            results.append(ExtractedCode(
                                language=lang,
                                content=code,
                                source_agent=source_agent,
                                suggested_filename=path,
                            ))
        except json.JSONDecodeError:
            pass
    return results


def extract_code_blocks(
    text: str,
    source_agent: Optional[str] = None,
    path_candidates: Optional[List[str]] = None,
    block_start_index: int = 0,
) -> List[ExtractedCode]:
    """Extract all code blocks from a text string.

    Parses:
    1. JSON format [{"path": "...", "language": "...", "code": "..."}] (from agent prompt)
    2. Markdown-style fenced code blocks (```language ... ```)
    Checks text before each code block for filepath hints; if none, uses path_candidates
    by global block index when provided (from transcript-wide path list).

    Args:
        text: The text to extract code from.
        source_agent: Optional agent name for attribution.
        path_candidates: Optional ordered list of path hints from full transcript.
        block_start_index: Global index of first block in this text (for path_candidates).

    Returns:
        List of ExtractedCode objects.
    """
    # First try JSON format (agent-instructed output)
    json_blocks = _extract_json_code_blocks(text, source_agent)
    if json_blocks:
        return json_blocks

    blocks = []
    for i, match in enumerate(CODE_BLOCK_PATTERN.finditer(text)):
        language = (match.group(1) or "text").lower()
        content = match.group(2).strip()

        if not content:
            continue

        ext = LANG_EXTENSIONS.get(language, ".txt")

        # Check for filepath hint in text before this code block
        text_before = text[:match.start()]
        filepath_hint = _detect_filepath_hint(text_before)

        if filepath_hint:
            filename = filepath_hint
        elif path_candidates and (block_start_index + i) < len(path_candidates):
            filename = path_candidates[block_start_index + i]
        else:
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


def generate_requirements(artifacts: List[dict]) -> str:
    """Scan Python code artifacts for import statements and generate requirements.txt content.

    Args:
        artifacts: List of artifact dicts with 'content', 'language' keys.

    Returns:
        Requirements.txt content string (one package per line).
    """
    packages: Set[str] = set()

    for artifact in artifacts:
        if artifact.get("language") not in ("python", "py"):
            continue

        content = artifact.get("content", "")
        # Match: import foo, from foo import bar, from foo.bar import baz
        for match in re.finditer(r"^(?:from|import)\s+(\w+)", content, re.MULTILINE):
            module = match.group(1)
            if module in PYTHON_STDLIB:
                continue
            if module in IMPORT_TO_PACKAGE:
                packages.add(IMPORT_TO_PACKAGE[module])
            elif module.isidentifier() and not module.startswith("_"):
                # Unknown third-party package — use module name as-is
                packages.add(module)

    return "\n".join(sorted(packages))


def extract_from_meeting_messages(
    messages: List[dict],
) -> List[ExtractedCode]:
    """Extract code blocks from a list of meeting messages.

    Uses filepath hints from each block's preceding text; also collects path-like
    strings (e.g. src/main.py) from the full transcript in order and assigns them
    to blocks that have no hint, so meeting-described folder structure is preserved.

    Args:
        messages: List of dicts with 'content', 'agent_name', 'role' keys.

    Returns:
        All code blocks found across all messages.
    """
    full_text = "\n\n".join(m.get("content", "") or "" for m in messages)
    path_candidates = _collect_path_candidates_from_text(full_text)

    all_blocks = []
    block_start = 0
    for msg in messages:
        content = msg.get("content") or ""
        blocks = extract_code_blocks(
            content,
            source_agent=msg.get("agent_name"),
            path_candidates=path_candidates if path_candidates else None,
            block_start_index=block_start,
        )
        all_blocks.extend(blocks)
        block_start += len(blocks)
    return all_blocks

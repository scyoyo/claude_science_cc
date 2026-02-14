"""
CodeExtractor: Extracts code blocks from meeting messages.

Parses markdown-style code fences (```language ... ```) from agent responses
and creates structured code artifacts.
"""

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


def extract_code_blocks(
    text: str,
    source_agent: Optional[str] = None,
) -> List[ExtractedCode]:
    """Extract all code blocks from a text string.

    Parses markdown-style fenced code blocks (```language ... ```).
    Checks text before each code block for filepath hints.

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

        # Check for filepath hint in text before this code block
        text_before = text[:match.start()]
        filepath_hint = _detect_filepath_hint(text_before)

        if filepath_hint:
            filename = filepath_hint
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

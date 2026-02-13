"""Input sanitization utilities."""

import re

# Pattern to match HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Pattern to match common script injection attempts
_SCRIPT_RE = re.compile(
    r"(javascript:|on\w+\s*=|<script|</script|&#x|&#\d+;)",
    re.IGNORECASE,
)


def strip_html_tags(text: str) -> str:
    """Remove HTML tags from text."""
    return _HTML_TAG_RE.sub("", text)


def sanitize_text(text: str) -> str:
    """Sanitize user input: strip HTML tags and script patterns."""
    text = strip_html_tags(text)
    text = _SCRIPT_RE.sub("", text)
    return text.strip()

"""
Simple language detection for agent response preference.

Priority: user's first input language > system locale.
Used to instruct LLM to respond in the same language (e.g. zh vs en).
"""

import re


def detect_language(text: str) -> str:
    """Detect language from text. Returns 'zh' for Chinese, 'en' otherwise.

    Uses a simple heuristic: proportion of CJK (or CJK punctuation) characters.
    """
    if not (text and text.strip()):
        return "en"
    text = text.strip()
    # CJK unified ranges (simplified: common Chinese, Japanese, Korean)
    cjk_pattern = re.compile(
        r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]"
    )
    cjk_count = sum(1 for c in text if cjk_pattern.match(c))
    total_meaningful = sum(1 for c in text if not c.isspace())
    if total_meaningful == 0:
        return "en"
    if cjk_count / total_meaningful >= 0.15:
        return "zh"
    return "en"


def language_instruction(preferred_lang: str) -> str:
    """Return the instruction line to append to system/user prompt for response language."""
    if preferred_lang == "zh":
        return "Respond in Chinese (中文)."
    return "Respond in English."


def meeting_preferred_lang(
    existing_messages: list,
    topic: str | None,
    locale: str | None,
) -> str:
    """Agent language for meetings: first user message in meeting, else topic, else locale. Returns 'zh' or 'en'."""
    for msg in existing_messages:
        if getattr(msg, "role", None) == "user" and getattr(msg, "content", None):
            return detect_language(msg.content)
    if topic and topic.strip():
        return detect_language(topic)
    if locale in ("zh", "en"):
        return locale
    return "en"

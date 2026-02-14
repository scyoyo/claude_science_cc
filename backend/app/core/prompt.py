"""Shared prompt generation for agents."""

from typing import Optional

from app.models import Agent


def generate_system_prompt(agent: Agent, language: Optional[str] = None) -> str:
    """Generate system prompt from agent fields.

    Args:
        agent: Agent model instance.
        language: Optional language code ("zh", "en"). When set, appends a
                  language instruction so the agent responds in the correct language.
    """
    prompt = (
        f"You are a {agent.title}. "
        f"Your expertise is in {agent.expertise}. "
        f"Your goal is to {agent.goal}. "
        f"Your role is to {agent.role}."
    )
    if language == "zh":
        prompt += "\n\nIMPORTANT: Always respond in Chinese (中文)."
    elif language and language != "en":
        prompt += f"\n\nIMPORTANT: Always respond in {language}."
    return prompt

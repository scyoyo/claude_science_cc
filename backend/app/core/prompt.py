"""Shared prompt generation for agents."""

from app.models import Agent


def generate_system_prompt(agent: Agent) -> str:
    """Generate system prompt from agent fields."""
    return (
        f"You are a {agent.title}. "
        f"Your expertise is in {agent.expertise}. "
        f"Your goal is to {agent.goal}. "
        f"Your role is to {agent.role}."
    )

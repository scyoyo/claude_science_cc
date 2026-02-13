"""
MeetingEngine: Orchestrates multi-agent conversations.

Manages turn-taking between agents, sends prompts to LLM providers,
and stores conversation messages. Supports round-robin discussion mode.

The LLM call is abstracted via a callable for easy mocking in tests.
"""

from typing import Callable, Dict, List, Optional

from app.schemas.onboarding import ChatMessage


# Type for LLM callable: (system_prompt, messages) -> response_text
LLMCallable = Callable[[str, List[ChatMessage]], str]


class MeetingEngine:
    """Orchestrates multi-agent meeting conversations.

    Args:
        llm_call: Callable that takes (system_prompt, messages) and returns response text.
                  This allows injection of real LLM calls or mocks for testing.
    """

    def __init__(self, llm_call: LLMCallable):
        self.llm_call = llm_call

    def run_round(
        self,
        agents: List[Dict],
        conversation_history: List[ChatMessage],
        topic: Optional[str] = None,
    ) -> List[Dict]:
        """Run one round of discussion where each agent speaks once.

        Args:
            agents: List of agent dicts with keys: id, name, system_prompt, model.
            conversation_history: Previous messages in the meeting.
            topic: Optional topic to focus the discussion.

        Returns:
            List of new messages generated in this round.
            Each message: {agent_id, agent_name, role, content}
        """
        new_messages = []

        for agent in agents:
            # Build the context for this agent
            messages = list(conversation_history)

            # Add topic as initial context if this is the start
            if topic and not messages:
                messages.append(ChatMessage(
                    role="user",
                    content=f"Discussion topic: {topic}",
                ))

            # Add new messages from this round so far
            for msg in new_messages:
                messages.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))

            # Call LLM for this agent
            response_text = self.llm_call(
                agent["system_prompt"],
                messages,
            )

            new_messages.append({
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "role": "assistant",
                "content": response_text,
            })

        return new_messages

    def run_meeting(
        self,
        agents: List[Dict],
        conversation_history: List[ChatMessage],
        rounds: int = 1,
        topic: Optional[str] = None,
    ) -> List[List[Dict]]:
        """Run multiple rounds of discussion.

        Args:
            agents: List of agent dicts.
            conversation_history: Previous messages.
            rounds: Number of rounds to run.
            topic: Optional discussion topic.

        Returns:
            List of rounds, each containing a list of messages.
        """
        all_rounds = []
        current_history = list(conversation_history)

        for round_num in range(rounds):
            round_messages = self.run_round(agents, current_history, topic if round_num == 0 else None)
            all_rounds.append(round_messages)

            # Add this round's messages to history for next round
            for msg in round_messages:
                current_history.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))

        return all_rounds

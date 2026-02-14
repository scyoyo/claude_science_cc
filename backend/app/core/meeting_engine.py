"""
MeetingEngine: Orchestrates multi-agent conversations with phase awareness.

Supports two modes:
- Structured mode (when agenda is provided): Team Lead drives discussion with
  phase-aware prompts (initial → synthesis → final structured output).
- Legacy mode (no agenda): Simple round-robin where every agent speaks each round.

The LLM call is abstracted via a callable for easy mocking in tests.
"""

from typing import Callable, Dict, List, Optional

from app.schemas.onboarding import ChatMessage
from app.core.meeting_prompts import (
    meeting_start_prompt,
    team_lead_initial_prompt,
    team_lead_synthesis_prompt,
    team_lead_final_prompt,
    team_member_prompt,
    phase_temperature,
    previous_context_prompt,
    CONCISENESS_RULE,
)


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
        """Run one round of discussion where each agent speaks once (legacy mode).

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
        """Run multiple rounds of discussion (legacy mode).

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

    # ==================== Structured Mode ====================

    def run_structured_round(
        self,
        agents: List[Dict],
        conversation_history: List[ChatMessage],
        round_num: int,
        num_rounds: int,
        agenda: str = "",
        agenda_questions: Optional[List[str]] = None,
        agenda_rules: Optional[List[str]] = None,
        output_type: str = "code",
        context_summaries: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Run one structured round with phase-aware prompts.

        Round 1: Team Lead proposes, members respond.
        Middle rounds: Team Lead synthesizes, members contribute.
        Final round: Team Lead only — produces structured output.

        Args:
            agents: List of agent dicts. First agent is Team Lead.
            conversation_history: Previous messages.
            round_num: Current round number (1-indexed).
            num_rounds: Total rounds planned.
            agenda: Meeting agenda text.
            agenda_questions: Questions to answer by end of meeting.
            agenda_rules: Constraint rules.
            output_type: "code", "report", or "paper".

        Returns:
            List of messages for this round.
        """
        if not agents:
            return []

        questions = agenda_questions or []
        rules = agenda_rules or []
        team_lead = agents[0]
        members = agents[1:]
        new_messages = []

        # Inject meeting start context on the first round
        if round_num == 1:
            conversation_history = list(conversation_history)

            # Inject previous meeting context if available
            if context_summaries:
                ctx_prompt = previous_context_prompt(context_summaries)
                if ctx_prompt:
                    conversation_history.append(ChatMessage(
                        role="user",
                        content=ctx_prompt,
                    ))

            start_context = meeting_start_prompt(
                team_lead_name=team_lead["name"],
                member_names=[m["name"] for m in members],
                agenda=agenda,
                agenda_questions=questions,
                agenda_rules=rules,
                num_rounds=num_rounds,
            )
            conversation_history.append(ChatMessage(
                role="user",
                content=start_context,
            ))

        # Final round: only Team Lead speaks
        if round_num >= num_rounds and num_rounds > 1:
            final_prompt = team_lead_final_prompt(
                team_lead_name=team_lead["name"],
                agenda=agenda,
                questions=questions,
                rules=rules,
                output_type=output_type,
            )
            messages = list(conversation_history)
            messages.append(ChatMessage(role="user", content=final_prompt))

            response = self.llm_call(team_lead["system_prompt"], messages)
            new_messages.append({
                "agent_id": team_lead["id"],
                "agent_name": team_lead["name"],
                "role": "assistant",
                "content": response,
            })
            return new_messages

        # Non-final rounds: Team Lead first, then members

        # Team Lead prompt
        if round_num == 1:
            lead_prompt = team_lead_initial_prompt(team_lead["name"])
        else:
            lead_prompt = team_lead_synthesis_prompt(team_lead["name"], round_num, num_rounds)

        lead_messages = list(conversation_history)
        lead_messages.append(ChatMessage(role="user", content=lead_prompt))

        lead_response = self.llm_call(team_lead["system_prompt"], lead_messages)
        new_messages.append({
            "agent_id": team_lead["id"],
            "agent_name": team_lead["name"],
            "role": "assistant",
            "content": lead_response,
        })

        # Members respond
        for member in members:
            member_prompt_text = team_member_prompt(member["name"], round_num, num_rounds)

            messages = list(conversation_history)
            # Include messages from this round so far
            for msg in new_messages:
                messages.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))
            messages.append(ChatMessage(role="user", content=member_prompt_text))

            response = self.llm_call(member["system_prompt"], messages)
            new_messages.append({
                "agent_id": member["id"],
                "agent_name": member["name"],
                "role": "assistant",
                "content": response,
            })

        return new_messages

    def run_structured_meeting(
        self,
        agents: List[Dict],
        conversation_history: List[ChatMessage],
        rounds: int = 1,
        agenda: str = "",
        agenda_questions: Optional[List[str]] = None,
        agenda_rules: Optional[List[str]] = None,
        output_type: str = "code",
        start_round: int = 1,
        context_summaries: Optional[List[Dict]] = None,
    ) -> List[List[Dict]]:
        """Run a full structured meeting across multiple rounds.

        Args:
            agents: List of agent dicts. First agent is Team Lead.
            conversation_history: Previous messages.
            rounds: Number of rounds to run.
            agenda: Meeting agenda text.
            agenda_questions: Questions to answer.
            agenda_rules: Constraint rules.
            output_type: "code", "report", or "paper".
            start_round: Starting round number (1-indexed, for resuming).

        Returns:
            List of rounds, each containing a list of messages.
        """
        all_rounds = []
        current_history = list(conversation_history)
        total_rounds = start_round + rounds - 1

        for i in range(rounds):
            current_round = start_round + i
            round_messages = self.run_structured_round(
                agents=agents,
                conversation_history=current_history,
                round_num=current_round,
                num_rounds=total_rounds,
                agenda=agenda,
                agenda_questions=agenda_questions,
                agenda_rules=agenda_rules,
                output_type=output_type,
                context_summaries=context_summaries if current_round == start_round else None,
            )
            all_rounds.append(round_messages)

            # Add this round's messages to history
            for msg in round_messages:
                current_history.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))

        return all_rounds

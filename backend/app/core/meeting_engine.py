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
    team_lead_final_prompt_synthesis_only,
    team_member_prompt,
    team_meeting_critic_prompt,
    integrator_consolidation_prompt,
    phase_temperature,
    previous_context_prompt,
    CONCISENESS_RULE,
    NO_CODE_FOR_NON_CODING,
    SCIENTIFIC_CRITIC,
    individual_meeting_start_prompt,
    individual_meeting_critic_prompt,
    individual_meeting_agent_revision_prompt,
    create_merge_prompt,
)
from app.core.agent_roles import sort_agents_for_meeting, is_coding_role, detect_integrator


# Type for LLM callable: (system_prompt, messages) -> response_text
LLMCallable = Callable[[str, List[ChatMessage]], str]


def build_individual_agents(agent: Dict) -> List[Dict]:
    """Construct [agent, synthetic_critic] for individual meeting via structured path.

    The agent becomes Team Lead, and a synthetic Scientific Critic is injected.
    sort_agents_for_meeting() will detect the critic by the 'role' field.
    """
    return [
        agent,
        {
            "id": None,
            "name": SCIENTIFIC_CRITIC["name"],
            "system_prompt": SCIENTIFIC_CRITIC["system_prompt"],
            "model": agent.get("model", "gpt-4"),
            "title": "Scientific Critic",
            "role": "critic",
        },
    ]


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
        preferred_lang: Optional[str] = None,
    ) -> List[Dict]:
        """Run one round of discussion where each agent speaks once (legacy mode).

        Args:
            agents: List of agent dicts with keys: id, name, system_prompt, model.
            conversation_history: Previous messages in the meeting.
            topic: Optional topic to focus the discussion.
            preferred_lang: Optional language code ("zh", "en") for response language.

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

            # Inject language instruction for first round when no prior messages
            if preferred_lang and not conversation_history:
                from app.core.lang_detect import language_instruction
                messages.append(ChatMessage(
                    role="user",
                    content=f"IMPORTANT: {language_instruction(preferred_lang)}",
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
        preferred_lang: Optional[str] = None,
    ) -> List[List[Dict]]:
        """Run multiple rounds of discussion (legacy mode).

        Args:
            agents: List of agent dicts.
            conversation_history: Previous messages.
            rounds: Number of rounds to run.
            topic: Optional discussion topic.
            preferred_lang: Optional language code ("zh", "en") for response language.

        Returns:
            List of rounds, each containing a list of messages.
        """
        all_rounds = []
        current_history = list(conversation_history)

        for round_num in range(rounds):
            round_messages = self.run_round(
                agents, current_history,
                topic if round_num == 0 else None,
                preferred_lang=preferred_lang if round_num == 0 else None,
            )
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
        preferred_lang: Optional[str] = None,
        round_plan: Optional[Dict] = None,
    ) -> List[Dict]:
        """Run one structured round with phase-aware prompts.

        Round 1: Team Lead proposes, members respond, critic evaluates.
        Middle rounds: Team Lead synthesizes, members contribute, critic evaluates.
        Final round: Team Lead only — produces structured output.

        Args:
            agents: List of agent dicts. PI/Lead auto-detected; Critic auto-separated.
            conversation_history: Previous messages.
            round_num: Current round number (1-indexed).
            num_rounds: Total rounds planned.
            agenda: Meeting agenda text.
            agenda_questions: Questions to answer by end of meeting.
            agenda_rules: Constraint rules.
            output_type: "code", "report", or "paper".
            round_plan: Optional dict with 'goal', 'title', 'expected_output' for this round.

        Returns:
            List of messages for this round.
        """
        if not agents:
            return []

        questions = agenda_questions or []
        rules = agenda_rules or []

        # Auto-detect roles: PI/Lead, Members, Critic
        team_lead, members, critic = sort_agents_for_meeting(agents)
        new_messages = []

        # Inject round plan goal into conversation context
        if round_plan:
            goal = round_plan.get("goal", "")
            if goal:
                conversation_history = list(conversation_history)
                conversation_history.append(ChatMessage(
                    role="user",
                    content=f"## Round {round_num} Goal\n{goal}",
                ))

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
                preferred_lang=preferred_lang,
                critic_name=critic["name"] if critic else None,
            )
            conversation_history.append(ChatMessage(
                role="user",
                content=start_context,
            ))

        # Final round: only Team Lead speaks (no critic)
        if round_num >= num_rounds and num_rounds > 1:
            if output_type == "code" and not is_coding_role(team_lead):
                final_prompt = team_lead_final_prompt_synthesis_only(
                    team_lead_name=team_lead["name"],
                    agenda=agenda,
                    questions=questions,
                )
            else:
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

        # Non-final rounds: Team Lead first, then members, then critic

        # Team Lead prompt
        if round_num == 1:
            lead_prompt = team_lead_initial_prompt(team_lead["name"])
        else:
            lead_prompt = team_lead_synthesis_prompt(team_lead["name"], round_num, num_rounds)
        if output_type == "code" and not is_coding_role(team_lead):
            lead_prompt = lead_prompt + "\n\n" + NO_CODE_FOR_NON_CODING

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
            if output_type == "code" and not is_coding_role(member):
                member_prompt_text = member_prompt_text + "\n\n" + NO_CODE_FOR_NON_CODING

            messages = list(conversation_history)
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

        # Critic evaluates (non-final rounds only)
        if critic:
            critic_prompt_text = team_meeting_critic_prompt(
                critic["name"], round_num, num_rounds,
            )
            if output_type == "code" and not is_coding_role(critic):
                critic_prompt_text = critic_prompt_text + "\n\n" + NO_CODE_FOR_NON_CODING
            messages = list(conversation_history)
            for msg in new_messages:
                messages.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))
            messages.append(ChatMessage(role="user", content=critic_prompt_text))

            response = self.llm_call(critic["system_prompt"], messages)
            new_messages.append({
                "agent_id": critic["id"],
                "agent_name": critic["name"],
                "role": "assistant",
                "content": response,
            })

        # Integrator step (code meetings): one agent consolidates code into folder structure
        if output_type == "code":
            integrator = detect_integrator(team_lead, members, critic)
            integrator_prompt = integrator_consolidation_prompt(integrator["name"])
            messages = list(conversation_history)
            for msg in new_messages:
                messages.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))
            messages.append(ChatMessage(role="user", content=integrator_prompt))
            response = self.llm_call(integrator["system_prompt"], messages)
            new_messages.append({
                "agent_id": integrator["id"],
                "agent_name": integrator["name"],
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
        preferred_lang: Optional[str] = None,
        round_plans: Optional[List[Dict]] = None,
    ) -> List[List[Dict]]:
        """Run a full structured meeting across multiple rounds.

        Args:
            agents: List of agent dicts. PI/Lead auto-detected.
            conversation_history: Previous messages.
            rounds: Number of rounds to run.
            agenda: Meeting agenda text.
            agenda_questions: Questions to answer.
            agenda_rules: Constraint rules.
            output_type: "code", "report", or "paper".
            start_round: Starting round number (1-indexed, for resuming).
            round_plans: Optional list of dicts with 'round', 'goal', 'title', 'expected_output'.

        Returns:
            List of rounds, each containing a list of messages.
        """
        all_rounds = []
        current_history = list(conversation_history)
        total_rounds = start_round + rounds - 1
        plans_by_round = {}
        if round_plans:
            for rp in round_plans:
                plans_by_round[rp.get("round", 0)] = rp

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
                preferred_lang=preferred_lang,
                round_plan=plans_by_round.get(current_round),
            )
            all_rounds.append(round_messages)

            # Add this round's messages to history
            for msg in round_messages:
                current_history.append(ChatMessage(
                    role="user",
                    content=f"[{msg['agent_name']}]: {msg['content']}",
                ))

        return all_rounds

    # ==================== Individual Meeting (Agent + Critic) ====================

    def run_individual_meeting(
        self,
        agent: Dict,
        conversation_history: List[ChatMessage],
        rounds: int = 3,
        agenda: str = "",
        agenda_questions: Optional[List[str]] = None,
        agenda_rules: Optional[List[str]] = None,
        context_summaries: Optional[List[Dict]] = None,
        preferred_lang: Optional[str] = None,
        output_type: str = "report",
        round_plans: Optional[List[Dict]] = None,
    ) -> List[List[Dict]]:
        """Run an individual meeting: agent + synthetic Scientific Critic.

        Now routes through the structured meeting engine. The agent becomes
        Team Lead, and a synthetic Scientific Critic is injected. This gives
        individual meetings all team meeting features (integrator, round_plans,
        SSE streaming via background runner, etc.).

        Returns:
            List of rounds, each containing a list of messages.
        """
        agents = build_individual_agents(agent)
        return self.run_structured_meeting(
            agents=agents,
            conversation_history=conversation_history,
            rounds=rounds,
            agenda=agenda,
            agenda_questions=agenda_questions,
            agenda_rules=agenda_rules,
            output_type=output_type,
            context_summaries=context_summaries,
            preferred_lang=preferred_lang,
            round_plans=round_plans,
        )

    # ==================== Merge Meeting ====================

    def run_merge_meeting(
        self,
        agents: List[Dict],
        source_summaries: List[Dict],
        conversation_history: List[ChatMessage],
        rounds: int = 2,
        agenda: str = "",
        agenda_questions: Optional[List[str]] = None,
        agenda_rules: Optional[List[str]] = None,
        output_type: str = "code",
        preferred_lang: Optional[str] = None,
    ) -> List[List[Dict]]:
        """Run a merge meeting that synthesizes multiple source discussions.

        Injects merge context, then runs a short structured meeting where
        the team synthesizes the best components from each source.

        Returns:
            List of rounds, each containing a list of messages.
        """
        merge_prompt = create_merge_prompt(
            agenda=agenda,
            source_summaries=source_summaries,
            questions=agenda_questions,
            rules=agenda_rules,
        )
        enriched_history = list(conversation_history)
        enriched_history.append(ChatMessage(role="user", content=merge_prompt))

        return self.run_structured_meeting(
            agents=agents,
            conversation_history=enriched_history,
            rounds=rounds,
            agenda=agenda,
            agenda_questions=agenda_questions,
            agenda_rules=agenda_rules,
            output_type=output_type,
            preferred_lang=preferred_lang,
        )

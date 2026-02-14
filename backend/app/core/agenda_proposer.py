"""
Agenda Proposal Strategies for meetings.

Provides 4 strategies for generating meeting agendas:
- ai_auto: AI generates agenda + questions + rules based on team composition
- agent_voting: Each agent proposes agenda items
- chain: Based on previous meeting results, suggest next meeting agenda
- recommend: AI recommends which strategy is best for the situation
"""

import json
from typing import Callable, Dict, List, Optional

from app.schemas.onboarding import ChatMessage


LLMCallable = Callable[[str, List[ChatMessage]], str]


class AgendaProposer:
    def __init__(self, llm_call: LLMCallable):
        self.llm_call = llm_call

    def auto_generate(
        self,
        agents: List[Dict],
        team_desc: str,
        goal: str,
        prev_meetings: Optional[List[Dict]] = None,
    ) -> Dict:
        """AI generates agenda + questions + rules based on team composition & goals.

        Returns: {"agenda": str, "questions": list[str], "rules": list[str]}
        """
        agent_descriptions = "\n".join(
            f"- {a['name']} ({a.get('title', '')}): {a.get('expertise', '')}"
            for a in agents
        )

        prev_context = ""
        if prev_meetings:
            prev_context = "\n\nPrevious meetings:\n" + "\n".join(
                f"- {m['title']}" for m in prev_meetings
            )

        system_prompt = (
            "You are an expert meeting facilitator. Generate a structured meeting agenda "
            "based on the team composition and goals. Return valid JSON only."
        )
        user_message = (
            f"Team description: {team_desc}\n"
            f"Goal: {goal}\n"
            f"Team members:\n{agent_descriptions}"
            f"{prev_context}\n\n"
            f"Generate a meeting agenda as JSON with keys: "
            f'"agenda" (string), "questions" (list of strings), "rules" (list of strings), '
            f'"suggested_rounds" (integer 1-10, how many discussion rounds are appropriate).'
        )

        response = self.llm_call(system_prompt, [ChatMessage(role="user", content=user_message)])
        return _parse_agenda_json(response)

    def agent_voting(
        self,
        agents: List[Dict],
        topic: str,
    ) -> Dict:
        """Each agent proposes 2-3 agenda items based on their expertise.

        Returns: {"proposals": [{"agent_name": str, "proposals": [str]}], "merged_agenda": str}
        """
        all_proposals = []

        for agent in agents:
            system_prompt = agent.get("system_prompt", "You are a helpful assistant.")
            user_message = (
                f"Topic: {topic}\n\n"
                f"As {agent['name']}, propose 2-3 specific agenda items for a team meeting "
                f"on this topic. Return a JSON array of strings."
            )
            response = self.llm_call(system_prompt, [ChatMessage(role="user", content=user_message)])
            proposals = _parse_proposals(response)
            all_proposals.append({
                "agent_name": agent["name"],
                "proposals": proposals,
            })

        # Merge proposals into a unified agenda
        all_items = []
        for p in all_proposals:
            all_items.extend(p["proposals"])

        merged = "; ".join(all_items[:6]) if all_items else topic

        return {
            "proposals": all_proposals,
            "merged_agenda": merged,
        }

    def chain_recommend(
        self,
        prev_meeting_summaries: List[Dict],
    ) -> Dict:
        """Based on previous results, suggest next meeting agenda.

        Extracts 'Next Steps' from completed meetings.

        Returns: {"agenda": str, "questions": list[str], "rules": list[str]}
        """
        if not prev_meeting_summaries:
            return {"agenda": "", "questions": [], "rules": []}

        summaries_text = "\n\n".join(
            f"Meeting: {s['title']}\nSummary: {s['summary']}"
            for s in prev_meeting_summaries
        )

        system_prompt = (
            "You are an expert meeting facilitator. Based on completed meeting results, "
            "suggest the next meeting's agenda. Focus on 'Next Steps' and unresolved items. "
            "Return valid JSON only."
        )
        user_message = (
            f"Previous meeting results:\n{summaries_text}\n\n"
            f"Generate a follow-up meeting agenda as JSON with keys: "
            f'"agenda" (string), "questions" (list of strings), "rules" (list of strings).'
        )

        response = self.llm_call(system_prompt, [ChatMessage(role="user", content=user_message)])
        return _parse_agenda_json(response)

    def recommend_strategy(
        self,
        agents: List[Dict],
        has_prev: bool,
        topic: str,
    ) -> Dict:
        """Recommend which agenda strategy is best for the situation.

        Rules:
        - has_prev → chain (continue from previous work)
        - many agents (>3) → agent_voting (leverage diverse perspectives)
        - else → ai_auto (general purpose)

        Returns: {"recommended": str, "reasoning": str}
        """
        if has_prev:
            return {
                "recommended": "chain",
                "reasoning": (
                    "Previous meetings exist. Chain strategy continues from "
                    "where you left off, extracting next steps automatically."
                ),
            }
        if len(agents) > 3:
            return {
                "recommended": "agent_voting",
                "reasoning": (
                    f"With {len(agents)} agents, agent voting leverages diverse perspectives "
                    f"to crowdsource the best agenda items."
                ),
            }
        return {
            "recommended": "ai_auto",
            "reasoning": (
                "AI auto-generation is ideal for small teams without prior context. "
                "It creates a focused agenda based on team composition and goals."
            ),
        }


def _parse_agenda_json(response: str) -> Dict:
    """Parse LLM response as agenda JSON, with fallback."""
    try:
        # Try to extract JSON from the response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            raw_rounds = data.get("suggested_rounds", 3)
            try:
                suggested_rounds = max(1, min(10, int(raw_rounds)))
            except (TypeError, ValueError):
                suggested_rounds = 3
            return {
                "agenda": data.get("agenda", ""),
                "questions": data.get("questions", []),
                "rules": data.get("rules", []),
                "suggested_rounds": suggested_rounds,
            }
    except (json.JSONDecodeError, ValueError):
        pass
    return {"agenda": response.strip(), "questions": [], "rules": [], "suggested_rounds": 3}


def _parse_proposals(response: str) -> List[str]:
    """Parse LLM response as a JSON array of strings, with fallback."""
    try:
        start = response.find("[")
        end = response.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(response[start:end])
            return [str(item) for item in items if item]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: split by newlines
    lines = [l.strip().lstrip("- ").lstrip("* ") for l in response.strip().split("\n") if l.strip()]
    return lines[:3]

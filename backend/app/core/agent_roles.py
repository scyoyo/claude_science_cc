"""
Agent role detection: identifies PI/Lead, Critic, and regular Members
based on name, title, and role fields.

Used by MeetingEngine to order speakers and inject critic feedback.
"""

import re
from typing import Dict, List, Optional, Tuple


# Keywords (case-insensitive) for detecting special roles
_LEAD_KEYWORDS = re.compile(
    r"\b(principal\s*investigator|pi\b|team\s*lead|lead\s*scientist|"
    r"project\s*lead|director|head\s+of|chief|supervisor|coordinator)",
    re.IGNORECASE,
)

_CRITIC_KEYWORDS = re.compile(
    r"\b(critic|reviewer|evaluator|scientific\s*critic|peer\s*review)",
    re.IGNORECASE,
)


def detect_role(agent: Dict) -> str:
    """Detect agent role: 'lead', 'critic', or 'member'.

    Checks name, title, and role fields for keyword matches.
    """
    text = " ".join(
        str(agent.get(f, "") or "") for f in ("name", "title", "role")
    )

    if _CRITIC_KEYWORDS.search(text):
        return "critic"
    if _LEAD_KEYWORDS.search(text):
        return "lead"
    return "member"


def sort_agents_for_meeting(
    agents: List[Dict],
) -> Tuple[Dict, List[Dict], Optional[Dict]]:
    """Sort agents into (team_lead, members, critic_or_none).

    - PI/Lead keyword match -> team_lead (first match wins; fallback: agents[0])
    - Critic/Reviewer keyword match -> separated from members
    - Everyone else -> members

    Returns:
        (team_lead, members, critic_or_none)
    """
    if not agents:
        raise ValueError("agents list must not be empty")

    lead: Optional[Dict] = None
    critic: Optional[Dict] = None
    members: List[Dict] = []

    for agent in agents:
        role = detect_role(agent)
        if role == "lead" and lead is None:
            lead = agent
        elif role == "critic" and critic is None:
            critic = agent
        else:
            members.append(agent)

    # Fallback: if no explicit lead, use agents[0]
    if lead is None:
        if members:
            lead = members.pop(0)
        elif critic:
            # Edge case: only a critic — treat as lead
            lead = critic
            critic = None

    return lead, members, critic

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

_CODING_KEYWORDS = re.compile(
    r"\b(engineer|developer|programmer|coding|software\s*engineer|"
    r"ml\s*engineer|code\s*engineer|implementation|programming)",
    re.IGNORECASE,
)

_INTEGRATOR_KEYWORDS = re.compile(
    r"\b(integrator|integration|consolidat)",
    re.IGNORECASE,
)


def is_coding_role(agent: Dict) -> bool:
    """True if this agent is responsible for writing code (title/expertise/role)."""
    text = " ".join(
        str(agent.get(f, "") or "") for f in ("name", "title", "expertise", "role")
    )
    return bool(_CODING_KEYWORDS.search(text))


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


def detect_integrator(
    team_lead: Dict,
    members: List[Dict],
    critic: Optional[Dict],
) -> Dict:
    """Choose which agent acts as integrator (consolidates code in code meetings).

    Prefer a member with 'integrator' in title/role; else a coding member (engineer);
    otherwise use the team lead.
    """
    def has_integrator_keyword(a: Dict) -> bool:
        text = " ".join(str(a.get(f, "") or "") for f in ("title", "expertise", "role"))
        return bool(_INTEGRATOR_KEYWORDS.search(text))

    for m in members:
        if has_integrator_keyword(m):
            return m
    for m in members:
        if is_coding_role(m):
            return m
    return team_lead

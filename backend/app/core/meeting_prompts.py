"""
Meeting prompts: Phase-aware prompt generation for structured meetings.

Adapted from virtual-lab (zou-group) prompt design. Provides:
- Predefined rules (CODING_RULES, CONCISENESS_RULE)
- Meeting start/context prompts
- Team Lead phase prompts (initial, synthesis, final)
- Team Member prompts
- Output structure templates by output_type
"""

from typing import Dict, List, Optional


# ==================== Predefined Rules ====================

CODING_RULES = [
    "Your code must be self-contained (with appropriate imports) and complete.",
    "Your code may not include any undefined or unimplemented variables or functions.",
    "Your code may not include any pseudocode; it must be fully functioning code.",
    "Your code may not include any hard-coded examples.",
    "If your code needs user-provided values, write code to parse those values from the command line.",
    "Your code must be high quality, well-engineered, efficient, and well-documented.",
]

REPORT_RULES = [
    "Provide specific data and evidence to support your findings.",
    "Include methodology details so results are reproducible.",
]

PAPER_RULES = [
    "Follow academic paper structure (Abstract, Methods, Results, Discussion).",
    "Cite relevant prior work where applicable.",
]

CONCISENESS_RULE = (
    "Be direct and concise. Skip pleasantries, acknowledgments, and filler. "
    "Go straight to substance."
)

# output_type -> default rules
DEFAULT_RULES: Dict[str, List[str]] = {
    "code": CODING_RULES + [CONCISENESS_RULE],
    "report": REPORT_RULES + [CONCISENESS_RULE],
    "paper": PAPER_RULES + [CONCISENESS_RULE],
}


def get_default_rules(output_type: str) -> List[str]:
    """Return default agenda_rules for the given output_type."""
    return list(DEFAULT_RULES.get(output_type, [CONCISENESS_RULE]))


# ==================== Meeting Start Prompt ====================

def meeting_start_prompt(
    team_lead_name: str,
    member_names: List[str],
    agenda: str,
    agenda_questions: List[str],
    agenda_rules: List[str],
    num_rounds: int,
) -> str:
    """Generate the meeting start context prompt injected as the first user message."""
    parts = [
        f"## Meeting Setup",
        f"",
        f"**Team Lead:** {team_lead_name}",
        f"**Team Members:** {', '.join(member_names)}",
        f"**Number of Rounds:** {num_rounds}",
    ]

    if agenda:
        parts.append(f"")
        parts.append(f"## Agenda")
        parts.append(agenda)

    if agenda_questions:
        parts.append(f"")
        parts.append(f"## Questions to Answer")
        for i, q in enumerate(agenda_questions, 1):
            parts.append(f"{i}. {q}")

    if agenda_rules:
        parts.append(f"")
        parts.append(f"## Rules")
        for rule in agenda_rules:
            parts.append(f"- {rule}")

    return "\n".join(parts)


# ==================== Team Lead Prompts ====================

def team_lead_initial_prompt(team_lead_name: str) -> str:
    """Prompt for Team Lead in the first round: propose ideas and guiding questions."""
    return (
        f"{team_lead_name}, as the Team Lead, please:\n"
        f"1. Propose your initial approach to the agenda.\n"
        f"2. Identify key challenges or open questions.\n"
        f"3. Pose 2-3 specific questions for team members to address based on their expertise.\n\n"
        f"Be direct and focus on substance."
    )


def team_lead_synthesis_prompt(
    team_lead_name: str,
    round_num: int,
    num_rounds: int,
) -> str:
    """Prompt for Team Lead in middle rounds: synthesize and drive decisions."""
    return (
        f"{team_lead_name}, as Team Lead for round {round_num}/{num_rounds}:\n"
        f"1. Synthesize the key points from the previous discussion.\n"
        f"2. Identify areas of agreement and unresolved disagreements.\n"
        f"3. Make decisions where possible, explaining your reasoning.\n"
        f"4. Pose follow-up questions to push the discussion forward.\n\n"
        f"Focus on converging toward actionable outcomes."
    )


def team_lead_final_prompt(
    team_lead_name: str,
    agenda: str,
    questions: List[str],
    rules: List[str],
    output_type: str,
) -> str:
    """Prompt for Team Lead in the final round: structured output."""
    parts = [
        f"{team_lead_name}, this is the FINAL round. Produce a structured summary of the meeting.",
        f"",
    ]

    if questions:
        parts.append("Answer each agenda question explicitly:")
        for i, q in enumerate(questions, 1):
            parts.append(f"  {i}. {q}")
        parts.append("")

    parts.append("Use this output structure:")
    parts.append(output_structure_prompt(output_type, bool(questions)))

    if rules:
        parts.append("")
        parts.append("Remember these rules apply:")
        for rule in rules:
            parts.append(f"- {rule}")

    return "\n".join(parts)


# ==================== Team Member Prompts ====================

def team_member_prompt(
    member_name: str,
    round_num: int,
    num_rounds: int,
) -> str:
    """Prompt for team members: contribute expertise, can pass if nothing new."""
    if round_num == 1:
        return (
            f"{member_name}, provide your expert perspective on the agenda and "
            f"respond to the Team Lead's questions. "
            f"Be direct and focus on your area of expertise."
        )
    return (
        f"{member_name}, for round {round_num}/{num_rounds}:\n"
        f"- Respond to the Team Lead's follow-up questions.\n"
        f"- Provide additional insights from your expertise.\n"
        f"- If you have nothing new to add, simply say \"PASS\"."
    )


# ==================== Output Structure Templates ====================

def output_structure_prompt(output_type: str, has_questions: bool) -> str:
    """Return the expected output structure based on output_type."""
    sections = {
        "code": [
            "### Agenda",
            "Restate the meeting agenda and goals.",
            "",
            "### Summary of Discussion",
            "Key decisions and rationale.",
            "",
            *( ["### Answers to Agenda Questions",
                "Answer each question with references to the discussion.",
                ""] if has_questions else []),
            "### Code Artifacts",
            "Complete, runnable code with comments.",
            "",
            "### Usage Instructions",
            "How to run the code, required dependencies, expected inputs/outputs.",
            "",
            "### Next Steps",
            "Remaining tasks and follow-up items.",
        ],
        "report": [
            "### Agenda",
            "Restate the meeting agenda and goals.",
            "",
            "### Summary of Discussion",
            "Key decisions and rationale.",
            "",
            *( ["### Answers to Agenda Questions",
                "Answer each question with references to the discussion.",
                ""] if has_questions else []),
            "### Findings",
            "Detailed findings with supporting evidence.",
            "",
            "### Analysis",
            "Interpretation and implications of the findings.",
            "",
            "### Conclusions",
            "Final conclusions and recommendations.",
            "",
            "### Next Steps",
            "Remaining tasks and follow-up items.",
        ],
        "paper": [
            "### Agenda",
            "Restate the meeting agenda and goals.",
            "",
            "### Summary of Discussion",
            "Key decisions and rationale.",
            "",
            *( ["### Answers to Agenda Questions",
                "Answer each question with references to the discussion.",
                ""] if has_questions else []),
            "### Abstract",
            "Concise summary of the work.",
            "",
            "### Methods",
            "Detailed methodology.",
            "",
            "### Results",
            "Key results and data.",
            "",
            "### Discussion",
            "Interpretation, limitations, and future directions.",
        ],
    }
    template = sections.get(output_type, sections["code"])
    return "\n".join(template)


# ==================== Temperature by Phase ====================

def phase_temperature(round_num: int, num_rounds: int) -> float:
    """Return suggested temperature based on meeting phase.

    Round 1 (exploration): 0.8
    Middle rounds (synthesis): 0.4
    Final round (structured output): 0.2
    """
    if round_num == 1:
        return 0.8
    if round_num >= num_rounds:
        return 0.2
    return 0.4

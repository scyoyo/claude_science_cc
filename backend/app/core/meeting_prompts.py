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

# Prefix for user messages from humans (not from an agent) so the model treats them as high-priority feedback
HUMAN_FEEDBACK_PREFIX = "**Human feedback:** "


def content_for_user_message(
    role: str,
    agent_id: Optional[str],
    agent_name: Optional[str],
    content: str,
) -> str:
    """Format user message content for conversation_history. Prefix human feedback so agents recognize it."""
    if role != "user":
        return content
    if _is_human_feedback(agent_id, agent_name):
        return HUMAN_FEEDBACK_PREFIX + content
    return content


def _is_human_feedback(agent_id: Optional[str], agent_name: Optional[str]) -> bool:
    """True if this user message is from a human (no agent_id, and agent_name is User/Human Expert or empty)."""
    if agent_id and str(agent_id).strip():
        return False
    name = (agent_name or "").strip()
    return name in ("", "User", "Human Expert")


# ==================== Predefined Rules ====================

CODING_RULES = [
    "Your code must be self-contained (with appropriate imports) and complete.",
    "Your code may not include any undefined or unimplemented variables or functions.",
    "Your code may not include any pseudocode; it must be fully functioning code.",
    "Your code may not include any hard-coded examples.",
    "If your code needs user-provided values, write code to parse those values from the command line.",
    "Your code must be high quality, well-engineered, efficient, and well-documented "
    "(including docstrings, comments, and Python type hints if using Python).",
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


# Instruction for non-coding agents when output_type is "code"
NO_CODE_FOR_NON_CODING = (
    "Do not output full code blocks; provide recommendations and discussion only. "
    "Code will be produced by the coding-focused team members."
)

# When output_type is "code", inject this so agents output code in a parseable JSON format
CODE_OUTPUT_JSON_RULE = (
    "When you output code, use this exact JSON format so it can be parsed and displayed as files: "
    '{"files": [{"path": "relative/filepath.ext", "content": "<full file content>", "language": "python"}]}. '
    "Use relative paths (e.g. src/main.py). You may add brief explanation in plain text before or after the JSON block. "
    "Output valid JSON only: inside each \"content\" string escape newlines as \\n and quotes as \\\" so the whole payload is valid JSON. "
    "Prefer wrapping the JSON in a markdown code block: ```json\\n<your JSON>\\n``` so it parses reliably."
)


def system_prompt_for_meeting(system_prompt: str, output_type: str) -> str:
    """Append code-output JSON rule when meeting output_type is code. Otherwise return unchanged."""
    if (output_type or "").strip().lower() != "code":
        return system_prompt
    return system_prompt + "\n\n" + CODE_OUTPUT_JSON_RULE


def get_agenda_rules_for_agent(output_type: str, agent: Dict) -> List[str]:
    """Return agenda rules for this agent. When output_type is code, non-coding roles skip CODING_RULES."""
    from app.core.agent_roles import is_coding_role

    if output_type != "code":
        return get_default_rules(output_type)
    if is_coding_role(agent):
        return list(DEFAULT_RULES.get("code", [CONCISENESS_RULE]))
    return [CONCISENESS_RULE]


# ==================== Previous Context Prompt ====================

def previous_context_prompt(summaries: List[Dict]) -> str:
    """Generate context from previous meeting summaries.

    Uses explicit [begin summary N] / [end summary N] boundaries (virtual-lab style)
    so the model can distinguish each meeting's excerpt.

    Args:
        summaries: List of dicts with 'title' and 'summary' keys.

    Returns:
        Formatted context string to inject into meeting start.
    """
    if not summaries:
        return ""

    parts = [
        "## Context from Previous Meetings",
        "",
    ]
    for i, s in enumerate(summaries, 1):
        parts.append(f"[begin summary {i}]")
        parts.append(f"### Meeting {i}: {s['title']}")
        parts.append("")
        parts.append(s["summary"])
        parts.append("")
        parts.append(f"[end summary {i}]")
        parts.append("")

    parts.append(
        "The above are relevant excerpts from previous discussions. "
        "Use them to inform your responses in this meeting."
    )
    return "\n".join(parts)


# ==================== Meeting Start Prompt ====================

def meeting_start_prompt(
    team_lead_name: str,
    member_names: List[str],
    agenda: str,
    agenda_questions: List[str],
    agenda_rules: List[str],
    num_rounds: int,
    preferred_lang: Optional[str] = None,
    critic_name: Optional[str] = None,
) -> str:
    """Generate the meeting start context prompt injected as the first user message."""
    parts = [
        f"## Meeting Setup",
        f"",
        f"**Team Lead:** {team_lead_name}",
        f"**Team Members:** {', '.join(member_names)}",
    ]
    if critic_name:
        parts.append(f"**Critic:** {critic_name}")
    parts.append(f"**Number of Rounds:** {num_rounds}")

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

    parts.append(f"")
    parts.append(
        "If there are messages labeled as human expert feedback, treat them as "
        "high-priority input and address them in your response."
    )

    if preferred_lang:
        parts.append(f"")
        parts.append(
            "## Language\nRespond in Chinese (中文)." if preferred_lang == "zh"
            else "## Language\nRespond in English."
        )

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


def team_lead_final_prompt_synthesis_only(
    team_lead_name: str,
    agenda: str,
    questions: List[str],
) -> str:
    """Final round prompt for a non-coding Lead: synthesize and list code from members, do not write new code."""
    parts = [
        f"{team_lead_name}, this is the FINAL round. Produce a structured summary of the meeting.",
        "",
        "Do NOT write new code yourself. Instead:",
        "- Summarize the key code or artifacts that team members have proposed.",
        "- List filenames and brief descriptions for each code artifact.",
        "- Provide usage/run instructions if members suggested them.",
        "- Restate agenda, recommendations, and answers to agenda questions.",
        "",
    ]
    if questions:
        parts.append("Answer each agenda question explicitly:")
        for i, q in enumerate(questions, 1):
            parts.append(f"  {i}. {q}")
        parts.append("")
    return "\n".join(parts)


# ==================== Team Member Prompts ====================

def team_meeting_critic_prompt(
    critic_name: str,
    round_num: int,
    num_rounds: int,
) -> str:
    """Prompt for the critic in a team meeting: evaluate the round's discussion."""
    return (
        f"{critic_name}, please critically evaluate the discussion so far "
        f"(round {round_num}/{num_rounds}).\n"
        f"- Identify flaws in reasoning, missing considerations, or weak evidence.\n"
        f"- Validate whether the discussion addresses the agenda and questions.\n"
        f"- Suggest specific improvements for the next round.\n"
        f"- Be constructive but rigorous — every critique should include a suggestion.\n"
        f"- Be direct and concise."
    )


def integrator_consolidation_prompt(integrator_name: str) -> str:
    """Prompt for the integrator to consolidate code from the round."""
    return (
        f"{integrator_name}, consolidate all code contributions from this round into a single folder structure. "
        "Output exactly the JSON format requested in your instructions: {\"files\": [{\"path\": \"...\", \"content\": \"...\", \"language\": \"...\"}]}. "
        "Use valid JSON: escape newlines in file content as \\n and internal quotes as \\\". "
        "List filenames and ensure the project is runnable (e.g. entry point, dependencies). "
        "Do not duplicate code; integrate and document. "
        "If no code was contributed this round, summarize what was discussed and what files would be needed."
    )


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
    """Return the expected output structure based on output_type.

    Includes Team Member Input and Recommendation (virtual-lab style) and
    Answer + Justification per agenda question.
    """
    _agenda = [
        "### Agenda",
        "Restate the meeting agenda and goals.",
        "",
    ]
    _team_input = [
        "### Team Member Input",
        "Summarize the key points raised by each team member. Preserve important "
        "details for future meetings.",
        "",
    ]
    _recommendation = [
        "### Recommendation",
        "Provide your expert recommendation regarding the agenda. Consider each "
        "member's input but use your expertise to make a final decision; the "
        "recommendation can conflict with some members if well justified. Give a "
        "clear, specific, actionable recommendation and justify it.",
        "",
    ]
    _summary = [
        "### Summary of Discussion",
        "Key decisions and rationale.",
        "",
    ]
    _answers_block = (
        [
            "### Answers to Agenda Questions",
            "For each agenda question provide:",
            "Answer: A specific answer based on the discussion and your recommendation.",
            "Justification: A brief explanation of why you provided that answer.",
            "",
        ]
        if has_questions
        else []
    )
    sections = {
        "code": _agenda + _team_input + _recommendation + _summary + _answers_block + [
            "### Code Artifacts",
            "Complete, runnable code with comments.",
            "",
            "### Usage Instructions",
            "How to run the code, required dependencies, expected inputs/outputs.",
            "",
            "### Next Steps",
            "Remaining tasks and follow-up items.",
        ],
        "report": _agenda + _team_input + _recommendation + _summary + _answers_block + [
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
        "paper": _agenda + _team_input + _recommendation + _summary + _answers_block + [
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


# ==================== Individual Meeting Prompts ====================

SCIENTIFIC_CRITIC = {
    "name": "Scientific Critic",
    "system_prompt": (
        "You are a Scientific Critic. Your role is to critically evaluate scientific "
        "proposals, methodologies, and results. You should:\n"
        "- Suggest improvements that directly address the agenda and any agenda questions.\n"
        "- Prioritize simple solutions over unnecessarily complex ones; demand more "
        "detail where detail is lacking.\n"
        "- Validate whether the answer strictly adheres to the agenda and agenda "
        "questions; provide corrective feedback if it does not.\n"
        "- Identify potential flaws in reasoning or methodology, and point out missing "
        "controls, confounding variables, or alternative explanations.\n"
        "- Be constructive but rigorous—every critique should include a suggestion.\n"
        "- Only provide feedback; do not implement the answer yourself.\n"
        "- Be direct and concise."
    ),
}


def individual_meeting_start_prompt(
    agent_name: str,
    agenda: str,
    questions: List[str],
    rules: List[str],
    num_rounds: int,
    preferred_lang: Optional[str] = None,
) -> str:
    """Generate start prompt for an individual meeting with a critic."""
    parts = [
        f"## Individual Meeting",
        f"",
        f"**Participant:** {agent_name}",
        f"**Critic:** Scientific Critic",
        f"**Number of Rounds:** {num_rounds}",
    ]

    if agenda:
        parts.append(f"")
        parts.append(f"## Agenda")
        parts.append(agenda)

    if questions:
        parts.append(f"")
        parts.append(f"## Questions to Answer")
        for i, q in enumerate(questions, 1):
            parts.append(f"{i}. {q}")

    if rules:
        parts.append(f"")
        parts.append(f"## Rules")
        for rule in rules:
            parts.append(f"- {rule}")

    if preferred_lang:
        parts.append(f"")
        parts.append(
            "## Language\nRespond in Chinese (中文)." if preferred_lang == "zh"
            else "## Language\nRespond in English."
        )

    return "\n".join(parts)


def individual_meeting_critic_prompt(critic_name: str, agent_name: str) -> str:
    """Prompt for the critic to evaluate the agent's response (virtual-lab style)."""
    return (
        f"{critic_name}, please critically evaluate {agent_name}'s response. "
        "In your critique, suggest improvements that directly address the agenda and "
        "any agenda questions. Prioritize simple solutions over unnecessarily complex "
        "ones, but demand more detail where detail is lacking. Additionally, validate "
        "whether the answer strictly adheres to the agenda and any agenda questions "
        "and provide corrective feedback if it does not. Only provide feedback; "
        "do not implement the answer yourself. Be specific and actionable."
    )


def individual_meeting_agent_revision_prompt(critic_name: str, agent_name: str) -> str:
    """Prompt for the agent to revise based on critic feedback (virtual-lab style)."""
    return (
        f"{agent_name}, please revise your response based on {critic_name}'s feedback. "
        "Address each critique point and improve your answer. Remember that your "
        "ultimate goal is to make improvements that better address the agenda."
    )


# ==================== Merge Meeting Prompts ====================

def create_merge_prompt(
    agenda: str,
    source_summaries: List[Dict],
    questions: Optional[List[str]] = None,
    rules: Optional[List[str]] = None,
) -> str:
    """Prompt to merge N independent discussions into a consensus answer."""
    parts = [
        "## Merge Meeting",
        "",
        "You are synthesizing the results of multiple independent discussions on the same topic.",
        "",
    ]

    if agenda:
        parts.append(f"## Original Agenda")
        parts.append(agenda)
        parts.append("")

    parts.append("## Source Discussions")
    parts.append("")
    for i, s in enumerate(source_summaries, 1):
        parts.append(f"### Discussion {i}: {s['title']}")
        parts.append(s["summary"])
        parts.append("")

    parts.append("## Your Task")
    parts.append(
        "Synthesize the best components from each discussion. "
        "Identify areas of agreement and resolve disagreements. "
        "Produce a unified, high-quality answer using the same format as the "
        "individual answers. Additionally, explain which components of your "
        "answer came from which discussion and why you chose to include them."
    )

    if questions:
        parts.append("")
        parts.append("## Questions to Answer")
        for i, q in enumerate(questions, 1):
            parts.append(f"{i}. {q}")

    if rules:
        parts.append("")
        parts.append("## Rules")
        for rule in rules:
            parts.append(f"- {rule}")

    return "\n".join(parts)


# ==================== Rewrite Prompts ====================

def rewrite_meeting_prompt(
    original_output: str,
    feedback: str,
    agenda: str,
    questions: Optional[List[str]] = None,
) -> str:
    """Prompt to improve a previous meeting output based on feedback."""
    parts = [
        "## Rewrite / Improve",
        "",
        "You are improving a previous meeting's output based on specific feedback.",
        "",
        "## Original Output",
        original_output,
        "",
        "## Improvement Feedback",
        feedback,
        "",
    ]

    if agenda:
        parts.append("## Original Agenda")
        parts.append(agenda)
        parts.append("")

    if questions:
        parts.append("## Questions to Answer")
        for i, q in enumerate(questions, 1):
            parts.append(f"{i}. {q}")
        parts.append("")

    parts.append(
        "Revise and improve the original output, addressing all feedback points. "
        "Maintain what was good and fix what was identified as needing improvement. "
        "Do not change anything else beyond addressing the feedback."
    )

    return "\n".join(parts)


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

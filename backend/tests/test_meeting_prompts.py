"""Tests for meeting_prompts module (V11 Step 1).

Covers:
- Predefined rules and default rules lookup
- Meeting start prompt generation
- Team Lead prompts (initial, synthesis, final)
- Team Member prompts
- Output structure templates
- Phase temperature
"""

import pytest
from app.core.meeting_prompts import (
    CODING_RULES,
    REPORT_RULES,
    PAPER_RULES,
    CONCISENESS_RULE,
    DEFAULT_RULES,
    get_default_rules,
    meeting_start_prompt,
    team_lead_initial_prompt,
    team_lead_synthesis_prompt,
    team_lead_final_prompt,
    team_member_prompt,
    output_structure_prompt,
    phase_temperature,
)


class TestPredefinedRules:
    """Test predefined rule constants and lookup."""

    def test_coding_rules_nonempty(self):
        assert len(CODING_RULES) >= 5
        assert all(isinstance(r, str) for r in CODING_RULES)

    def test_report_rules_nonempty(self):
        assert len(REPORT_RULES) >= 1

    def test_paper_rules_nonempty(self):
        assert len(PAPER_RULES) >= 1

    def test_conciseness_rule_is_string(self):
        assert isinstance(CONCISENESS_RULE, str)
        assert "concise" in CONCISENESS_RULE.lower()

    def test_default_rules_code(self):
        rules = get_default_rules("code")
        assert CONCISENESS_RULE in rules
        for cr in CODING_RULES:
            assert cr in rules

    def test_default_rules_report(self):
        rules = get_default_rules("report")
        assert CONCISENESS_RULE in rules
        for rr in REPORT_RULES:
            assert rr in rules

    def test_default_rules_paper(self):
        rules = get_default_rules("paper")
        assert CONCISENESS_RULE in rules
        for pr in PAPER_RULES:
            assert pr in rules

    def test_default_rules_unknown_type(self):
        rules = get_default_rules("unknown")
        assert CONCISENESS_RULE in rules

    def test_default_rules_returns_copy(self):
        """get_default_rules returns a new list each time."""
        r1 = get_default_rules("code")
        r2 = get_default_rules("code")
        assert r1 == r2
        assert r1 is not r2


class TestMeetingStartPrompt:
    """Test meeting_start_prompt generation."""

    def test_basic_prompt(self):
        result = meeting_start_prompt(
            team_lead_name="Dr. Smith",
            member_names=["Dr. Jones", "Dr. Lee"],
            agenda="Design a protein folding pipeline",
            agenda_questions=["What algorithm to use?", "What dataset?"],
            agenda_rules=["Be concise"],
            num_rounds=3,
        )
        assert "Dr. Smith" in result
        assert "Dr. Jones" in result
        assert "Dr. Lee" in result
        assert "protein folding" in result
        assert "What algorithm to use?" in result
        assert "What dataset?" in result
        assert "Be concise" in result
        assert "3" in result

    def test_empty_agenda(self):
        result = meeting_start_prompt(
            team_lead_name="Lead",
            member_names=["A"],
            agenda="",
            agenda_questions=[],
            agenda_rules=[],
            num_rounds=1,
        )
        assert "Lead" in result
        assert "Agenda" not in result.split("## Meeting Setup")[1]  # no separate Agenda section

    def test_no_questions(self):
        result = meeting_start_prompt(
            team_lead_name="Lead",
            member_names=["A"],
            agenda="Topic",
            agenda_questions=[],
            agenda_rules=[],
            num_rounds=2,
        )
        assert "Questions to Answer" not in result

    def test_no_rules(self):
        result = meeting_start_prompt(
            team_lead_name="Lead",
            member_names=["A"],
            agenda="Topic",
            agenda_questions=[],
            agenda_rules=[],
            num_rounds=2,
        )
        assert "## Rules" not in result


class TestTeamLeadPrompts:
    """Test Team Lead prompt generation for each phase."""

    def test_initial_prompt(self):
        result = team_lead_initial_prompt("Dr. Smith")
        assert "Dr. Smith" in result
        assert "Team Lead" in result
        assert "initial" in result.lower() or "approach" in result.lower()

    def test_synthesis_prompt(self):
        result = team_lead_synthesis_prompt("Dr. Smith", 2, 5)
        assert "Dr. Smith" in result
        assert "2/5" in result
        assert "synthesize" in result.lower() or "Synthesize" in result

    def test_final_prompt_with_questions(self):
        result = team_lead_final_prompt(
            "Dr. Smith",
            agenda="Build ML pipeline",
            questions=["Which model?", "What metrics?"],
            rules=["No pseudocode"],
            output_type="code",
        )
        assert "FINAL" in result
        assert "Dr. Smith" in result
        assert "Which model?" in result
        assert "What metrics?" in result
        assert "No pseudocode" in result
        assert "Code Artifacts" in result

    def test_final_prompt_no_questions(self):
        result = team_lead_final_prompt(
            "Lead",
            agenda="",
            questions=[],
            rules=[],
            output_type="report",
        )
        assert "FINAL" in result
        assert "Findings" in result
        assert "Answers to Agenda Questions" not in result

    def test_final_prompt_paper_type(self):
        result = team_lead_final_prompt(
            "Lead",
            agenda="Write paper",
            questions=["Key contribution?"],
            rules=[],
            output_type="paper",
        )
        assert "Abstract" in result
        assert "Methods" in result
        assert "Results" in result
        assert "Discussion" in result


class TestTeamMemberPrompt:
    """Test team member prompt generation."""

    def test_first_round(self):
        result = team_member_prompt("Dr. Jones", 1, 5)
        assert "Dr. Jones" in result
        assert "expert" in result.lower() or "expertise" in result.lower()

    def test_middle_round(self):
        result = team_member_prompt("Dr. Jones", 3, 5)
        assert "Dr. Jones" in result
        assert "3/5" in result
        assert "PASS" in result

    def test_last_round_member(self):
        """Members in last round still get the middle-round prompt (only lead speaks final)."""
        result = team_member_prompt("Dr. Jones", 5, 5)
        assert "Dr. Jones" in result
        assert "PASS" in result


class TestOutputStructurePrompt:
    """Test output structure template generation."""

    def test_code_with_questions(self):
        result = output_structure_prompt("code", has_questions=True)
        assert "### Agenda" in result
        assert "### Code Artifacts" in result
        assert "### Usage Instructions" in result
        assert "### Answers to Agenda Questions" in result

    def test_code_without_questions(self):
        result = output_structure_prompt("code", has_questions=False)
        assert "### Code Artifacts" in result
        assert "### Answers to Agenda Questions" not in result

    def test_report(self):
        result = output_structure_prompt("report", has_questions=True)
        assert "### Findings" in result
        assert "### Analysis" in result
        assert "### Conclusions" in result

    def test_paper(self):
        result = output_structure_prompt("paper", has_questions=False)
        assert "### Abstract" in result
        assert "### Methods" in result
        assert "### Results" in result
        assert "### Discussion" in result

    def test_unknown_type_falls_back_to_code(self):
        result = output_structure_prompt("unknown", has_questions=False)
        assert "### Code Artifacts" in result


class TestPhaseTemperature:
    """Test phase-based temperature selection."""

    def test_first_round(self):
        assert phase_temperature(1, 5) == 0.8

    def test_middle_round(self):
        assert phase_temperature(2, 5) == 0.4
        assert phase_temperature(3, 5) == 0.4

    def test_final_round(self):
        assert phase_temperature(5, 5) == 0.2

    def test_single_round_meeting(self):
        """Single round: round 1 == final round, final takes precedence."""
        # round_num=1, num_rounds=1 → first round check triggers first → 0.8
        # This is intentional: with a single round we want exploration
        assert phase_temperature(1, 1) == 0.8

    def test_two_round_meeting(self):
        assert phase_temperature(1, 2) == 0.8  # first
        assert phase_temperature(2, 2) == 0.2  # final

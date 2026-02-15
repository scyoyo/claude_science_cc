"""Tests for agent role detection and sorting."""

import pytest
from app.core.agent_roles import detect_role, sort_agents_for_meeting


class TestDetectRole:
    """Tests for detect_role()."""

    def test_detect_role_lead_by_title(self):
        """Agent with 'Principal Investigator' in title is detected as lead."""
        agent = {"name": "Dr. Smith", "title": "Principal Investigator", "role": ""}
        assert detect_role(agent) == "lead"

    def test_detect_role_lead_by_role_field(self):
        """Agent with 'PI' in role field is detected as lead."""
        agent = {"name": "Dr. Jones", "title": "Biologist", "role": "PI"}
        assert detect_role(agent) == "lead"

    def test_detect_role_lead_by_name(self):
        """Agent with 'Team Lead' in name is detected as lead."""
        agent = {"name": "Team Lead Chen", "title": "", "role": ""}
        assert detect_role(agent) == "lead"

    def test_detect_role_critic_by_name(self):
        """Agent with 'Scientific Critic' in name is detected as critic."""
        agent = {"name": "Scientific Critic", "title": "", "role": ""}
        assert detect_role(agent) == "critic"

    def test_detect_role_critic_by_title(self):
        """Agent with 'Reviewer' in title is detected as critic."""
        agent = {"name": "Dr. Review", "title": "Peer Reviewer", "role": "scientist"}
        assert detect_role(agent) == "critic"

    def test_detect_role_member_default(self):
        """Agent with no special keywords is a member."""
        agent = {"name": "Dr. Data", "title": "Machine Learning Specialist", "role": "researcher"}
        assert detect_role(agent) == "member"

    def test_detect_role_missing_fields(self):
        """Missing fields don't crash — defaults to member."""
        agent = {"name": "Bob"}
        assert detect_role(agent) == "member"


class TestSortAgentsForMeeting:
    """Tests for sort_agents_for_meeting()."""

    def test_pi_detected_as_lead(self):
        """PI agent is sorted as team_lead even if not first."""
        agents = [
            {"id": "1", "name": "Data Analyst", "title": "Analyst", "role": ""},
            {"id": "2", "name": "Dr. Smith", "title": "Principal Investigator", "role": ""},
            {"id": "3", "name": "ML Engineer", "title": "Engineer", "role": ""},
        ]
        lead, members, critic = sort_agents_for_meeting(agents)
        assert lead["id"] == "2"
        assert len(members) == 2
        assert critic is None

    def test_critic_separated_from_members(self):
        """Critic agent is separated from members list."""
        agents = [
            {"id": "1", "name": "Dr. Lead", "title": "Principal Investigator", "role": ""},
            {"id": "2", "name": "Researcher", "title": "Biologist", "role": ""},
            {"id": "3", "name": "Scientific Critic", "title": "Critic", "role": ""},
        ]
        lead, members, critic = sort_agents_for_meeting(agents)
        assert lead["id"] == "1"
        assert critic["id"] == "3"
        assert len(members) == 1
        assert members[0]["id"] == "2"

    def test_no_special_roles_fallback(self):
        """Without lead keywords, first agent becomes lead."""
        agents = [
            {"id": "1", "name": "Alice", "title": "Biologist", "role": "researcher"},
            {"id": "2", "name": "Bob", "title": "Chemist", "role": "researcher"},
        ]
        lead, members, critic = sort_agents_for_meeting(agents)
        assert lead["id"] == "1"
        assert len(members) == 1
        assert critic is None

    def test_only_critic_becomes_lead(self):
        """If only one agent and it matches critic, it becomes lead."""
        agents = [
            {"id": "1", "name": "Scientific Critic", "title": "Critic", "role": ""},
        ]
        lead, members, critic = sort_agents_for_meeting(agents)
        assert lead["id"] == "1"
        assert critic is None
        assert members == []

    def test_empty_agents_raises(self):
        """Empty agent list raises ValueError."""
        with pytest.raises(ValueError):
            sort_agents_for_meeting([])

    def test_lead_and_critic_both_detected(self):
        """Both lead and critic detected from a 4-agent team."""
        agents = [
            {"id": "1", "name": "ML Engineer", "title": "Engineer", "role": ""},
            {"id": "2", "name": "Dr. PI", "title": "Principal Investigator", "role": "PI"},
            {"id": "3", "name": "Data Scientist", "title": "Scientist", "role": ""},
            {"id": "4", "name": "Scientific Critic", "title": "Reviewer", "role": ""},
        ]
        lead, members, critic = sort_agents_for_meeting(agents)
        assert lead["id"] == "2"
        assert critic["id"] == "4"
        assert set(m["id"] for m in members) == {"1", "3"}

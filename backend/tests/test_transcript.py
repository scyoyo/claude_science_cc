"""Tests for Meeting Transcript (V8 + V12 enhancements).

Covers:
- Transcript format with rounds and speakers
- Enhanced transcript with agenda, participants, output_type
- Artifact listing in transcript footer
"""

import pytest
from app.models import Meeting, MeetingMessage, CodeArtifact


class TestMeetingTranscript:
    def _setup_meeting(self, test_db, team_id, **kwargs):
        defaults = dict(
            team_id=team_id, title="ML Discussion",
            current_round=2, status="completed", max_rounds=5,
        )
        defaults.update(kwargs)
        meeting = Meeting(**defaults)
        test_db.add(meeting)
        test_db.commit()
        test_db.refresh(meeting)

        messages = [
            MeetingMessage(meeting_id=meeting.id, role="user", content="Let's discuss neural architectures.", round_number=1),
            MeetingMessage(meeting_id=meeting.id, role="assistant", agent_name="Alice", content="I suggest using transformers.", round_number=1),
            MeetingMessage(meeting_id=meeting.id, role="assistant", agent_name="Bob", content="Agreed. We should also consider CNNs.", round_number=1),
            MeetingMessage(meeting_id=meeting.id, role="assistant", agent_name="Alice", content="Transformers outperform CNNs for NLP.", round_number=2),
        ]
        test_db.add_all(messages)
        test_db.commit()
        return meeting

    def test_transcript_format(self, client, test_db):
        """Transcript is formatted markdown with rounds and speakers."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(test_db, team["id"])

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        assert resp.status_code == 200
        text = resp.text
        assert "# ML Discussion" in text
        assert "## Round 1" in text
        assert "## Round 2" in text
        assert "**Alice:**" in text
        assert "**Bob:**" in text
        assert "**User:**" in text

    def test_transcript_content_type(self, client, test_db):
        """Transcript returns markdown content type."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(test_db, team["id"])

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        assert "text/markdown" in resp.headers["content-type"]

    def test_transcript_empty_meeting(self, client):
        """Transcript for meeting with no messages."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"], "title": "Empty",
        }).json()

        resp = client.get(f"/api/meetings/{meeting['id']}/transcript")
        assert resp.status_code == 200
        assert "# Empty" in resp.text

    def test_transcript_not_found(self, client):
        """Transcript for nonexistent meeting returns 404."""
        resp = client.get("/api/meetings/nonexistent/transcript")
        assert resp.status_code == 404

    def test_transcript_has_metadata(self, client, test_db):
        """Transcript includes status and round info."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(test_db, team["id"])

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        text = resp.text
        assert "completed" in text
        assert "2/5" in text  # current_round/max_rounds

    def test_transcript_has_agenda(self, client, test_db):
        """Transcript includes agenda and output_type when present."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(
            test_db, team["id"],
            agenda="Build a protein folding pipeline",
            output_type="code",
        )

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        text = resp.text
        assert "Build a protein folding pipeline" in text
        assert "Output Type" in text

    def test_transcript_has_participants(self, client, test_db):
        """Transcript includes participant list."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(test_db, team["id"])

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        text = resp.text
        assert "Participants" in text
        assert "Alice" in text
        assert "Bob" in text

    def test_transcript_has_artifacts(self, client, test_db):
        """Transcript includes artifact listing when artifacts exist."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting(test_db, team["id"])

        # Add artifacts
        artifact = CodeArtifact(
            meeting_id=meeting.id,
            filename="pipeline.py",
            language="python",
            content="class Pipeline: pass",
        )
        test_db.add(artifact)
        test_db.commit()

        resp = client.get(f"/api/meetings/{meeting.id}/transcript")
        text = resp.text
        assert "## Artifacts" in text
        assert "`pipeline.py`" in text

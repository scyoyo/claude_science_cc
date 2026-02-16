import pytest
from app.models import Meeting, MeetingMessage


class TestMeetingSummary:
    def _setup_meeting_with_messages(self, test_db, team_id):
        """Create a meeting with several agent messages."""
        meeting = Meeting(team_id=team_id, title="Design Discussion", current_round=2, status="completed")
        test_db.add(meeting)
        test_db.commit()
        test_db.refresh(meeting)

        messages = [
            MeetingMessage(
                meeting_id=meeting.id,
                role="assistant",
                agent_name="Alice",
                content="We should use a transformer architecture for the model. It provides better attention mechanisms.",
                round_number=1,
            ),
            MeetingMessage(
                meeting_id=meeting.id,
                role="assistant",
                agent_name="Bob",
                content="I agree with the transformer approach. Additionally, we need to consider the dataset preprocessing pipeline.",
                round_number=1,
            ),
            MeetingMessage(
                meeting_id=meeting.id,
                role="user",
                content="What about computational cost?",
                round_number=1,
            ),
            MeetingMessage(
                meeting_id=meeting.id,
                role="assistant",
                agent_name="Alice",
                content="The computational cost can be managed with mixed precision training. This reduces memory by 50%.",
                round_number=2,
            ),
            MeetingMessage(
                meeting_id=meeting.id,
                role="assistant",
                agent_name="Bob",
                content="We should also implement gradient checkpointing. This further reduces memory at the cost of some speed.",
                round_number=2,
            ),
        ]
        test_db.add_all(messages)
        test_db.commit()
        return meeting

    def test_meeting_summary(self, client, test_db):
        """Get summary returns cached data only (participants, and round_summaries when present)."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = self._setup_meeting_with_messages(test_db, team["id"])
        # Pre-populate cached round summaries (as would be done during meeting run)
        meeting.cached_round_summaries = [
            {"round": 1, "summary_text": "Round 1 summary.", "key_points": ["Point A."]},
            {"round": 2, "summary_text": "Round 2 summary.", "key_points": ["Point B."]},
        ]
        test_db.commit()
        test_db.refresh(meeting)

        resp = client.get(f"/api/meetings/{meeting.id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_id"] == meeting.id
        assert data["title"] == "Design Discussion"
        assert data["total_rounds"] == 2
        assert data["total_messages"] == 5
        assert set(data["participants"]) == {"Alice", "Bob"}
        assert data["status"] == "completed"
        assert len(data["round_summaries"]) == 2
        assert data["round_summaries"][0]["round"] == 1
        assert data["round_summaries"][0]["summary_text"] == "Round 1 summary."
        assert data["round_summaries"][1]["round"] == 2

    def test_summary_empty_meeting(self, client):
        """Summary of meeting with no messages."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = client.post("/api/meetings/", json={
            "team_id": team["id"],
            "title": "Empty Meeting",
        }).json()

        resp = client.get(f"/api/meetings/{meeting['id']}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_messages"] == 0
        assert data["participants"] == []
        assert data["key_points"] == []

    def test_summary_not_found(self, client):
        """Summary for nonexistent meeting returns 404."""
        resp = client.get("/api/meetings/nonexistent/summary")
        assert resp.status_code == 404

    def test_summary_returns_cached_full_summary(self, client, test_db):
        """When cached_summary_text / cached_key_points exist, GET returns them."""
        team = client.post("/api/teams/", json={"name": "Team"}).json()
        meeting = Meeting(team_id=team["id"], title="Test", current_round=1, status="completed")
        meeting.cached_summary_text = "Cached full summary."
        meeting.cached_key_points = ["Key one.", "Key two."]
        test_db.add(meeting)
        test_db.commit()
        test_db.refresh(meeting)

        resp = client.get(f"/api/meetings/{meeting.id}/summary")
        data = resp.json()
        assert data["summary_text"] == "Cached full summary."
        assert data["key_points"] == ["Key one.", "Key two."]

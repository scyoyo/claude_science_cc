"""Tests for team sharing/member management (V4 Phase 4.2)."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import Team
from app.models.user import User, UserTeamRole
from app.core.auth import hash_password, create_access_token


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _user(db, name="alice"):
    u = User(email=f"{name}@test.com", username=name, hashed_password=hash_password("pass1234"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _hdr(uid):
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


class TestTeamSharing:
    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_add_member(self, client, test_db):
        owner = _user(test_db, "owner")
        member = _user(test_db, "member")
        team = Team(name="Shared", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        resp = client.post(
            f"/api/teams/{team.id}/members",
            json={"user_id": member.id, "role": "editor"},
            headers=_hdr(owner.id),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "editor"
        assert resp.json()["user_id"] == member.id

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_update_member_role(self, client, test_db):
        owner = _user(test_db, "owner")
        member = _user(test_db, "member")
        team = Team(name="Shared", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        # Add as viewer
        client.post(
            f"/api/teams/{team.id}/members",
            json={"user_id": member.id, "role": "viewer"},
            headers=_hdr(owner.id),
        )

        # Upgrade to editor (re-post with same user_id)
        resp = client.post(
            f"/api/teams/{team.id}/members",
            json={"user_id": member.id, "role": "editor"},
            headers=_hdr(owner.id),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "editor"

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_list_members(self, client, test_db):
        owner = _user(test_db, "owner")
        m1 = _user(test_db, "alice")
        m2 = _user(test_db, "bob")
        team = Team(name="Team", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        for m, role in [(m1, "editor"), (m2, "viewer")]:
            test_db.add(UserTeamRole(user_id=m.id, team_id=team.id, role=role))
        test_db.commit()

        resp = client.get(f"/api/teams/{team.id}/members", headers=_hdr(owner.id))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_remove_member(self, client, test_db):
        owner = _user(test_db, "owner")
        member = _user(test_db, "member")
        team = Team(name="Team", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        role = UserTeamRole(user_id=member.id, team_id=team.id, role="editor")
        test_db.add(role)
        test_db.commit()

        resp = client.delete(
            f"/api/teams/{team.id}/members/{member.id}",
            headers=_hdr(owner.id),
        )
        assert resp.status_code == 204

        # Verify removed
        resp = client.get(f"/api/teams/{team.id}/members", headers=_hdr(owner.id))
        assert len(resp.json()) == 0

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_non_owner_cannot_add_member(self, client, test_db):
        owner = _user(test_db, "owner")
        editor = _user(test_db, "editor")
        other = _user(test_db, "other")
        team = Team(name="Team", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        test_db.add(UserTeamRole(user_id=editor.id, team_id=team.id, role="editor"))
        test_db.commit()

        resp = client.post(
            f"/api/teams/{team.id}/members",
            json={"user_id": other.id, "role": "viewer"},
            headers=_hdr(editor.id),
        )
        assert resp.status_code == 403

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_add_nonexistent_user(self, client, test_db):
        owner = _user(test_db, "owner")
        team = Team(name="Team", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        resp = client.post(
            f"/api/teams/{team.id}/members",
            json={"user_id": "nonexistent-id", "role": "viewer"},
            headers=_hdr(owner.id),
        )
        assert resp.status_code == 404

    def test_v1_compat_members_list(self, client, test_db):
        """V1 mode (no auth) should still work."""
        team = Team(name="V1 Team")
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        resp = client.get(f"/api/teams/{team.id}/members")
        assert resp.status_code == 200
        assert resp.json() == []

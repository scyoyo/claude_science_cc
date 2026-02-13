"""Tests for RBAC permissions (V3 Phase 3.2).

Tests cover:
- Permission checks (owner, editor, viewer, no access)
- Team CRUD with auth: create sets owner, list filters by access, update/delete require roles
- V1 backward compat: all operations pass when AUTH_ENABLED=False
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import Team
from app.models.user import User, UserTeamRole
from app.core.auth import hash_password, create_access_token
from app.core.permissions import get_team_role, check_team_access


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


def _create_user(db, username="alice", email="alice@test.com", is_admin=False):
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password("password123"),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user_id: str) -> dict:
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


# ==================== Permission Logic Tests ====================


class TestGetTeamRole:
    def test_owner_by_owner_id(self, test_db):
        user = _create_user(test_db)
        team = Team(name="My Team", owner_id=user.id)
        test_db.add(team)
        test_db.commit()
        assert get_team_role(test_db, user, team) == "owner"

    def test_admin_gets_owner_role(self, test_db):
        admin = _create_user(test_db, username="admin", email="admin@test.com", is_admin=True)
        team = Team(name="Other Team")
        test_db.add(team)
        test_db.commit()
        assert get_team_role(test_db, admin, team) == "owner"

    def test_explicit_editor_role(self, test_db):
        user = _create_user(test_db)
        team = Team(name="Shared Team")
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        role = UserTeamRole(user_id=user.id, team_id=team.id, role="editor")
        test_db.add(role)
        test_db.commit()

        assert get_team_role(test_db, user, team) == "editor"

    def test_public_team_gives_viewer(self, test_db):
        user = _create_user(test_db)
        team = Team(name="Public Team", is_public=True)
        test_db.add(team)
        test_db.commit()
        assert get_team_role(test_db, user, team) == "viewer"

    def test_no_access_to_private_team(self, test_db):
        user = _create_user(test_db)
        team = Team(name="Private Team", is_public=False)
        test_db.add(team)
        test_db.commit()
        assert get_team_role(test_db, user, team) is None

    def test_none_user_returns_none(self, test_db):
        team = Team(name="Any Team")
        test_db.add(team)
        test_db.commit()
        assert get_team_role(test_db, None, team) is None


class TestCheckTeamAccess:
    def test_none_user_always_passes(self, test_db):
        team = Team(name="Any Team")
        test_db.add(team)
        test_db.commit()
        # Should not raise
        check_team_access(test_db, None, team, min_role="owner")

    def test_owner_passes_all_levels(self, test_db):
        user = _create_user(test_db)
        team = Team(name="My Team", owner_id=user.id)
        test_db.add(team)
        test_db.commit()
        for role in ["viewer", "editor", "owner"]:
            check_team_access(test_db, user, team, min_role=role)

    def test_viewer_cannot_edit(self, test_db):
        user = _create_user(test_db)
        team = Team(name="Public", is_public=True)
        test_db.add(team)
        test_db.commit()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            check_team_access(test_db, user, team, min_role="editor")
        assert exc.value.status_code == 403

    def test_no_access_raises_404(self, test_db):
        user = _create_user(test_db)
        team = Team(name="Private")
        test_db.add(team)
        test_db.commit()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            check_team_access(test_db, user, team, min_role="viewer")
        assert exc.value.status_code == 404


# ==================== Team API with Auth Tests ====================


class TestTeamCRUDWithAuth:
    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_create_team_sets_owner(self, client, test_db):
        user = _create_user(test_db)
        resp = client.post(
            "/api/teams/",
            json={"name": "Auth Team"},
            headers=_auth_header(user.id),
        )
        assert resp.status_code == 201
        data = resp.json()
        # Verify owner_id was set
        team = test_db.query(Team).filter(Team.id == data["id"]).first()
        assert team.owner_id == user.id

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_owner_can_delete(self, client, test_db):
        user = _create_user(test_db)
        team = Team(name="Delete Me", owner_id=user.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        resp = client.delete(f"/api/teams/{team.id}", headers=_auth_header(user.id))
        assert resp.status_code == 204

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_non_owner_cannot_delete(self, client, test_db):
        owner = _create_user(test_db, username="owner", email="owner@test.com")
        other = _create_user(test_db, username="other", email="other@test.com")

        team = Team(name="Protected", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        # Editor can't delete
        role = UserTeamRole(user_id=other.id, team_id=team.id, role="editor")
        test_db.add(role)
        test_db.commit()

        resp = client.delete(f"/api/teams/{team.id}", headers=_auth_header(other.id))
        assert resp.status_code == 403

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_editor_can_update(self, client, test_db):
        owner = _create_user(test_db, username="owner", email="owner@test.com")
        editor = _create_user(test_db, username="editor", email="editor@test.com")

        team = Team(name="Editable", owner_id=owner.id)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        role = UserTeamRole(user_id=editor.id, team_id=team.id, role="editor")
        test_db.add(role)
        test_db.commit()

        resp = client.put(
            f"/api/teams/{team.id}",
            json={"name": "Updated"},
            headers=_auth_header(editor.id),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_viewer_cannot_update(self, client, test_db):
        owner = _create_user(test_db, username="owner", email="owner@test.com")
        viewer = _create_user(test_db, username="viewer", email="viewer@test.com")

        team = Team(name="ReadOnly", owner_id=owner.id, is_public=True)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        resp = client.put(
            f"/api/teams/{team.id}",
            json={"name": "Hacked"},
            headers=_auth_header(viewer.id),
        )
        assert resp.status_code == 403

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_list_teams_filters_by_access(self, client, test_db):
        user = _create_user(test_db)
        other = _create_user(test_db, username="other", email="other@test.com")

        # User's own team
        t1 = Team(name="My Team", owner_id=user.id)
        # Other user's private team
        t2 = Team(name="Private Team", owner_id=other.id, is_public=False)
        # Public team
        t3 = Team(name="Public Team", is_public=True)
        test_db.add_all([t1, t2, t3])
        test_db.commit()

        resp = client.get("/api/teams/", headers=_auth_header(user.id))
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["items"]]
        assert "My Team" in names
        assert "Public Team" in names
        assert "Private Team" not in names

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_unauthenticated_gets_401(self, client):
        resp = client.get("/api/teams/")
        assert resp.status_code == 401

    @patch("app.config.settings.AUTH_ENABLED", True)
    def test_admin_can_access_all_teams(self, client, test_db):
        admin = _create_user(test_db, username="admin", email="admin@test.com", is_admin=True)
        other = _create_user(test_db, username="other", email="other@test.com")

        team = Team(name="Private", owner_id=other.id, is_public=False)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        # Admin can view
        resp = client.get(f"/api/teams/{team.id}", headers=_auth_header(admin.id))
        assert resp.status_code == 200

        # Admin can delete
        resp = client.delete(f"/api/teams/{team.id}", headers=_auth_header(admin.id))
        assert resp.status_code == 204

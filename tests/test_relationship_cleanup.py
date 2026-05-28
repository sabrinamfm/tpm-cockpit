"""Tests for Relationship cleanup when linked objects are deleted (M2).

For each of the 8 object types, verifies:
  - Deleting an object removes relationships where it is the source
  - Deleting an object removes relationships where it is the target
  - Deleting the object does not remove unrelated relationships
Covers both the API delete path and the UI delete path.
"""

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_program(client) -> dict:
    return client.post("/programs", json={"name": "P"}).json()


def _make_work_item(client, program_id: int, title="WI") -> dict:
    return client.post(
        f"/programs/{program_id}/work-items",
        json={"title": title, "status": "open", "priority": "medium"},
    ).json()


def _make_dependency(client, program_id: int, title="DEP") -> dict:
    return client.post(
        f"/programs/{program_id}/dependencies",
        json={"title": title, "status": "open"},
    ).json()


def _make_risk(client, program_id: int, title="RSK") -> dict:
    return client.post(
        f"/programs/{program_id}/risks",
        json={"title": title, "severity": "medium", "likelihood": "possible", "status": "open"},
    ).json()


def _make_status_report(client, program_id: int) -> dict:
    return client.post(
        f"/programs/{program_id}/status-reports",
        json={"report_date": "2026-01-01", "reported_health": "on_track", "summary": "ok"},
    ).json()


def _make_milestone(client, program_id: int, title="MS") -> dict:
    return client.post(
        f"/programs/{program_id}/milestones",
        json={"title": title, "status": "planned"},
    ).json()


def _make_decision(client, program_id: int, title="DEC") -> dict:
    return client.post(
        f"/programs/{program_id}/decisions",
        json={"title": title, "status": "proposed"},
    ).json()


def _make_requirement(client, program_id: int, title="REQ") -> dict:
    return client.post(
        f"/programs/{program_id}/requirements",
        json={"title": title, "source_type": "customer_commitment", "status": "proposed"},
    ).json()


def _make_feature(client, program_id: int, title="FEA") -> dict:
    return client.post(
        f"/programs/{program_id}/features",
        json={"title": title, "status": "proposed"},
    ).json()


def _make_relationship(client, program_id: int, src_type, src_id, tgt_type, tgt_id, rel_type="blocks") -> dict:
    return client.post(
        "/relationships",
        json={
            "source_type": src_type,
            "source_id": src_id,
            "target_type": tgt_type,
            "target_id": tgt_id,
            "relationship_type": rel_type,
        },
    ).json()


def _list_relationships(client, program_id: int) -> list:
    return client.get(f"/programs/{program_id}/relationships").json()


# ── API delete path ────────────────────────────────────────────────────────────

class TestApiDeleteCleansUpRelationships:
    def test_work_item_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        wi = _make_work_item(client, pid)
        risk = _make_risk(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "risk", risk["id"])

        client.delete(f"/work-items/{wi['id']}")
        assert _list_relationships(client, pid) == []

    def test_work_item_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        wi = _make_work_item(client, pid)
        risk = _make_risk(client, pid)
        _make_relationship(client, pid, "risk", risk["id"], "work_item", wi["id"])

        client.delete(f"/work-items/{wi['id']}")
        assert _list_relationships(client, pid) == []

    def test_dependency_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dep = _make_dependency(client, pid)
        risk = _make_risk(client, pid)
        _make_relationship(client, pid, "dependency", dep["id"], "risk", risk["id"])

        client.delete(f"/dependencies/{dep['id']}")
        assert _list_relationships(client, pid) == []

    def test_dependency_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dep = _make_dependency(client, pid)
        risk = _make_risk(client, pid)
        _make_relationship(client, pid, "risk", risk["id"], "dependency", dep["id"])

        client.delete(f"/dependencies/{dep['id']}")
        assert _list_relationships(client, pid) == []

    def test_risk_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        risk = _make_risk(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "risk", risk["id"], "work_item", wi["id"])

        client.delete(f"/risks/{risk['id']}")
        assert _list_relationships(client, pid) == []

    def test_risk_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        risk = _make_risk(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "risk", risk["id"])

        client.delete(f"/risks/{risk['id']}")
        assert _list_relationships(client, pid) == []

    def test_status_report_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        report = _make_status_report(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "status_report", report["id"], "work_item", wi["id"])

        client.delete(f"/status-reports/{report['id']}")
        assert _list_relationships(client, pid) == []

    def test_status_report_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        report = _make_status_report(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "status_report", report["id"])

        client.delete(f"/status-reports/{report['id']}")
        assert _list_relationships(client, pid) == []

    def test_milestone_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        ms = _make_milestone(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "milestone", ms["id"], "work_item", wi["id"])

        client.delete(f"/milestones/{ms['id']}")
        assert _list_relationships(client, pid) == []

    def test_milestone_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        ms = _make_milestone(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "milestone", ms["id"])

        client.delete(f"/milestones/{ms['id']}")
        assert _list_relationships(client, pid) == []

    def test_decision_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dec = _make_decision(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "decision", dec["id"], "work_item", wi["id"])

        client.delete(f"/decisions/{dec['id']}")
        assert _list_relationships(client, pid) == []

    def test_decision_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dec = _make_decision(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "decision", dec["id"])

        client.delete(f"/decisions/{dec['id']}")
        assert _list_relationships(client, pid) == []

    def test_requirement_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        req = _make_requirement(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "requirement", req["id"], "work_item", wi["id"])

        client.delete(f"/requirements/{req['id']}")
        assert _list_relationships(client, pid) == []

    def test_requirement_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        req = _make_requirement(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "requirement", req["id"])

        client.delete(f"/requirements/{req['id']}")
        assert _list_relationships(client, pid) == []

    def test_feature_as_source(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        fea = _make_feature(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "feature", fea["id"], "work_item", wi["id"])

        client.delete(f"/features/{fea['id']}")
        assert _list_relationships(client, pid) == []

    def test_feature_as_target(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        fea = _make_feature(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "feature", fea["id"])

        client.delete(f"/features/{fea['id']}")
        assert _list_relationships(client, pid) == []

    def test_unrelated_relationship_preserved(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        wi1 = _make_work_item(client, pid, "WI1")
        wi2 = _make_work_item(client, pid, "WI2")
        wi3 = _make_work_item(client, pid, "WI3")
        rel = _make_relationship(client, pid, "work_item", wi2["id"], "work_item", wi3["id"])
        _make_relationship(client, pid, "work_item", wi1["id"], "work_item", wi2["id"])

        client.delete(f"/work-items/{wi1['id']}")
        remaining = _list_relationships(client, pid)
        assert len(remaining) == 1
        assert remaining[0]["id"] == rel["id"]


# ── UI delete path ─────────────────────────────────────────────────────────────

class TestUiDeleteCleansUpRelationships:
    def test_work_item_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        wi = _make_work_item(client, pid)
        risk = _make_risk(client, pid)
        _make_relationship(client, pid, "work_item", wi["id"], "risk", risk["id"])

        client.post(f"/work-items/{wi['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_dependency_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dep = _make_dependency(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "dependency", dep["id"], "work_item", wi["id"])

        client.post(f"/dependencies/{dep['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_risk_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        risk = _make_risk(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "risk", risk["id"], "work_item", wi["id"])

        client.post(f"/risks/{risk['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_status_report_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        report = _make_status_report(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "status_report", report["id"], "work_item", wi["id"])

        client.post(f"/status-reports/{report['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_milestone_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        ms = _make_milestone(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "milestone", ms["id"], "work_item", wi["id"])

        client.post(f"/milestones/{ms['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_decision_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        dec = _make_decision(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "decision", dec["id"], "work_item", wi["id"])

        client.post(f"/decisions/{dec['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_requirement_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        req = _make_requirement(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "requirement", req["id"], "work_item", wi["id"])

        client.post(f"/requirements/{req['id']}/delete")
        assert _list_relationships(client, pid) == []

    def test_feature_ui_delete(self, client):
        prog = _make_program(client)
        pid = prog["id"]
        fea = _make_feature(client, pid)
        wi = _make_work_item(client, pid)
        _make_relationship(client, pid, "feature", fea["id"], "work_item", wi["id"])

        client.post(f"/features/{fea['id']}/delete")
        assert _list_relationships(client, pid) == []

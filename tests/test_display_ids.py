"""Tests for stable display IDs on core objects."""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_program(client, name="Test Program"):
    return client.post("/programs", json={"name": name}).json()


def _create_work_item(client, program_id, title="Task"):
    return client.post(
        f"/programs/{program_id}/work-items",
        json={"title": title},
    ).json()


def _create_dependency(client, program_id, title="Dep"):
    return client.post(
        f"/programs/{program_id}/dependencies",
        json={"title": title, "dependency_type": "team", "status": "open", "blocking_level": "medium"},
    ).json()


def _create_risk(client, program_id, title="Risk"):
    return client.post(
        f"/programs/{program_id}/risks",
        json={"title": title, "severity": "medium", "likelihood": "possible", "status": "open"},
    ).json()


def _create_status_report(client, program_id):
    return client.post(
        f"/programs/{program_id}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()


# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------


def test_program_display_id_generated(client):
    data = _create_program(client)
    assert data["display_id"] is not None
    assert data["display_id"].startswith("PRG-")


def test_work_item_display_id_generated(client):
    p = _create_program(client)
    data = _create_work_item(client, p["id"])
    assert data["display_id"] is not None
    assert data["display_id"].startswith("WI-")


def test_dependency_display_id_generated(client):
    p = _create_program(client)
    data = _create_dependency(client, p["id"])
    assert data["display_id"] is not None
    assert data["display_id"].startswith("DEP-")


def test_risk_display_id_generated(client):
    p = _create_program(client)
    data = _create_risk(client, p["id"])
    assert data["display_id"] is not None
    assert data["display_id"].startswith("RSK-")


def test_status_report_display_id_generated(client):
    p = _create_program(client)
    data = _create_status_report(client, p["id"])
    assert data["display_id"] is not None
    assert data["display_id"].startswith("SR-")


# ---------------------------------------------------------------------------
# Format tests
# ---------------------------------------------------------------------------


def test_program_display_id_format(client):
    data = _create_program(client)
    parts = data["display_id"].split("-")
    assert parts[0] == "PRG"
    assert len(parts[1]) == 3
    assert parts[1].isdigit()


def test_work_item_display_id_format(client):
    p = _create_program(client)
    data = _create_work_item(client, p["id"])
    parts = data["display_id"].split("-")
    assert parts[0] == "WI"
    assert len(parts[1]) == 3
    assert parts[1].isdigit()


def test_display_id_encodes_pk(client):
    data = _create_program(client)
    expected = f"PRG-{data['id']:03d}"
    assert data["display_id"] == expected


# ---------------------------------------------------------------------------
# Uniqueness tests
# ---------------------------------------------------------------------------


def test_program_display_ids_unique(client):
    p1 = _create_program(client, "Prog A")
    p2 = _create_program(client, "Prog B")
    p3 = _create_program(client, "Prog C")
    ids = {p1["display_id"], p2["display_id"], p3["display_id"]}
    assert len(ids) == 3


def test_cross_type_display_ids_distinguished_by_prefix(client):
    p = _create_program(client)
    wi = _create_work_item(client, p["id"])
    assert p["display_id"].startswith("PRG-")
    assert wi["display_id"].startswith("WI-")
    assert p["display_id"] != wi["display_id"]


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


def test_display_id_persists_on_get(client):
    p = _create_program(client)
    original_display_id = p["display_id"]
    fetched = client.get(f"/programs/{p['id']}").json()
    assert fetched["display_id"] == original_display_id


def test_display_id_unchanged_after_update(client):
    p = _create_program(client)
    original_display_id = p["display_id"]
    client.patch(f"/programs/{p['id']}", json={"name": "Updated Name"})
    fetched = client.get(f"/programs/{p['id']}").json()
    assert fetched["display_id"] == original_display_id


# ---------------------------------------------------------------------------
# API exposure tests
# ---------------------------------------------------------------------------


def test_program_api_returns_display_id(client):
    p = _create_program(client)
    resp = client.get(f"/programs/{p['id']}")
    assert resp.status_code == 200
    assert resp.json()["display_id"] == p["display_id"]


def test_work_item_api_returns_display_id(client):
    p = _create_program(client)
    wi = _create_work_item(client, p["id"])
    resp = client.get(f"/work-items/{wi['id']}")
    assert resp.status_code == 200
    assert resp.json()["display_id"] == wi["display_id"]


def test_status_report_api_returns_display_id(client):
    p = _create_program(client)
    sr = _create_status_report(client, p["id"])
    resp = client.get(f"/status-reports/{sr['id']}")
    assert resp.status_code == 200
    assert resp.json()["display_id"] == sr["display_id"]


# ---------------------------------------------------------------------------
# UI display tests
# ---------------------------------------------------------------------------


def test_program_list_shows_display_id(client):
    p = _create_program(client, "Visible Program")
    resp = client.get("/")
    assert resp.status_code == 200
    assert p["display_id"] in resp.text


def test_program_detail_shows_display_id(client):
    p = _create_program(client, "Detail Program")
    resp = client.get(f"/programs/{p['id']}/view")
    assert resp.status_code == 200
    assert p["display_id"] in resp.text


def test_work_item_display_id_on_detail_page(client):
    p = _create_program(client)
    wi = _create_work_item(client, p["id"], "My Work Item")
    resp = client.get(f"/programs/{p['id']}/view")
    assert resp.status_code == 200
    assert wi["display_id"] in resp.text


def test_risk_display_id_on_detail_page(client):
    p = _create_program(client)
    r = _create_risk(client, p["id"], "My Risk")
    resp = client.get(f"/programs/{p['id']}/view")
    assert resp.status_code == 200
    assert r["display_id"] in resp.text


def test_dependency_display_id_on_detail_page(client):
    p = _create_program(client)
    dep = _create_dependency(client, p["id"], "My Dep")
    resp = client.get(f"/programs/{p['id']}/view")
    assert resp.status_code == 200
    assert dep["display_id"] in resp.text


def test_status_report_display_id_on_detail_page(client):
    p = _create_program(client)
    sr = _create_status_report(client, p["id"])
    resp = client.get(f"/programs/{p['id']}/view")
    assert resp.status_code == 200
    assert sr["display_id"] in resp.text

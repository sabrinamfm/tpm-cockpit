"""Tests for the Feature model, API, UI, filters, and relationship integration."""


# ── Feature API ───────────────────────────────────────────────────────────────

def test_create_feature_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/features",
        json={"title": "Dark Mode", "status": "planned", "target_date": "2026-09-01"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Dark Mode"
    assert body["status"] == "planned"
    assert body["target_date"] == "2026-09-01"
    assert body["display_id"].startswith("FT-")
    assert body["program_id"] == prog["id"]


def test_create_feature_invalid_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/features",
        json={"title": "F", "status": "not_a_status"},
    )
    assert resp.status_code == 422


def test_create_feature_program_not_found(client) -> None:
    resp = client.post("/programs/99999/features", json={"title": "F"})
    assert resp.status_code == 404


def test_list_features(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/features", json={"title": "F1"})
    client.post(f"/programs/{prog['id']}/features", json={"title": "F2"})
    resp = client.get(f"/programs/{prog['id']}/features")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_features_program_not_found(client) -> None:
    assert client.get("/programs/99999/features").status_code == 404


def test_get_feature(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F"}).json()
    resp = client.get(f"/features/{ft['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "F"


def test_get_feature_not_found(client) -> None:
    assert client.get("/features/99999").status_code == 404


def test_update_feature(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F", "status": "proposed"}).json()
    resp = client.patch(f"/features/{ft['id']}", json={"status": "in_progress", "title": "F Active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["title"] == "F Active"


def test_delete_feature(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F"}).json()
    assert client.delete(f"/features/{ft['id']}").status_code == 204
    assert client.get(f"/features/{ft['id']}").status_code == 404


def test_delete_feature_not_found(client) -> None:
    assert client.delete("/features/99999").status_code == 404


def test_feature_display_ids_are_unique(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    f1 = client.post(f"/programs/{prog['id']}/features", json={"title": "F1"}).json()
    f2 = client.post(f"/programs/{prog['id']}/features", json={"title": "F2"}).json()
    assert f1["display_id"] != f2["display_id"]
    assert f1["display_id"].startswith("FT-")
    assert f2["display_id"].startswith("FT-")


def test_feature_all_statuses_valid(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    for s in ("proposed", "planned", "in_progress", "blocked", "delivered", "deferred", "cancelled"):
        resp = client.post(f"/programs/{prog['id']}/features", json={"title": s, "status": s})
        assert resp.status_code == 201, f"status {s!r} should be valid"
        assert resp.json()["status"] == s


def test_feature_with_all_fields(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(f"/programs/{prog['id']}/features", json={
        "title": "Full Feature",
        "description": "A full feature",
        "status": "in_progress",
        "owner": "Alice",
        "target_date": "2026-10-01",
        "link": "https://example.com/feature",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner"] == "Alice"
    assert body["target_date"] == "2026-10-01"
    assert body["link"] == "https://example.com/feature"
    assert body["description"] == "A full feature"


# ── Feature UI ────────────────────────────────────────────────────────────────

def test_program_detail_shows_features_section(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Features" in resp.text
    assert "new-feature" in resp.text


def test_program_detail_shows_feature_row(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/features",
        json={"title": "Search", "status": "in_progress", "owner": "Bob", "target_date": "2026-11-01"},
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "Search" in resp.text
    assert "In Progress" in resp.text
    assert "2026-11-01" in resp.text
    assert "Bob" in resp.text


def test_program_detail_shows_feature_link(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(
        f"/programs/{prog['id']}/features",
        json={"title": "Linked Feature", "link": "https://example.com/feat"},
    )
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert "https://example.com/feat" in resp.text


def test_create_feature_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/features/create",
        data={"title": "Export CSV", "status": "planned"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"
    features = client.get(f"/programs/{prog['id']}/features").json()
    assert len(features) == 1
    assert features[0]["title"] == "Export CSV"


def test_create_feature_via_ui_missing_title(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/features/create",
        data={"title": "", "status": "planned"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "show_new_feature=1" in resp.headers["location"]


def test_deliver_feature_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(
        f"/programs/{prog['id']}/features",
        json={"title": "F", "status": "in_progress"},
    ).json()
    resp = client.post(f"/features/{ft['id']}/deliver-ui", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/features/{ft['id']}").json()["status"] == "delivered"


def test_delete_feature_via_ui(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F"}).json()
    resp = client.post(f"/features/{ft['id']}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert client.get(f"/features/{ft['id']}").status_code == 404


def test_edit_feature_panel_opens_inline(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "Inline Feature"}).json()
    resp = client.get(f"/programs/{prog['id']}/view?edit_feature_id={ft['id']}")
    assert resp.status_code == 200
    assert '<details id="edit-feature" class="collapsible-panel" open>' in resp.text
    assert "Inline Feature" in resp.text


# ── Feature filters ───────────────────────────────────────────────────────────

def test_feature_filter_by_status(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/features", json={"title": "Planned feature", "status": "planned"})
    client.post(f"/programs/{prog['id']}/features", json={"title": "Blocked feature", "status": "blocked"})
    resp = client.get(f"/programs/{prog['id']}/view?feature_status_filter=planned")
    assert resp.status_code == 200
    assert "Planned feature" in resp.text
    assert "</span>Blocked feature" not in resp.text


def test_feature_filter_by_owner(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    client.post(f"/programs/{prog['id']}/features", json={"title": "Alice feature", "owner": "Alice"})
    client.post(f"/programs/{prog['id']}/features", json={"title": "Bob feature", "owner": "Bob"})
    resp = client.get(f"/programs/{prog['id']}/view?feature_owner_filter=Alice")
    assert resp.status_code == 200
    assert "Alice feature" in resp.text
    assert "</span>Bob feature" not in resp.text


# ── Feature + Relationship integration ───────────────────────────────────────

def test_create_relationship_with_feature(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F"}).json()
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R"}).json()
    resp = client.post("/relationships", json={
        "source_type": "feature",
        "source_id": ft["id"],
        "relationship_type": "tracks",
        "target_type": "requirement",
        "target_id": req["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "feature"
    assert resp.json()["display_id"].startswith("REL-")


def test_feature_appears_in_relationship_picker(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "My Feature"}).json()
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert ft["display_id"] in resp.text
    assert "My Feature" in resp.text


def test_feature_relationship_shown_on_detail_page(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "Feature"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "MS"}).json()
    client.post("/relationships", json={
        "source_type": "feature", "source_id": ft["id"],
        "relationship_type": "tracks", "target_type": "milestone", "target_id": ms["id"],
    })
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert ft["display_id"] in resp.text
    assert "tracks" in resp.text


def test_program_relationships_includes_feature_relationships(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F"}).json()
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "D"}).json()
    client.post("/relationships", json={
        "source_type": "feature", "source_id": ft["id"],
        "relationship_type": "relates_to", "target_type": "decision", "target_id": dec["id"],
    })
    rels = client.get(f"/programs/{prog['id']}/relationships").json()
    assert len(rels) == 1
    assert rels[0]["source_type"] == "feature"

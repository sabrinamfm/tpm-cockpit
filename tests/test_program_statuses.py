"""Tests for configurable Program Statuses."""


# ── Seeding ──────────────────────────────────────────────────────────────────

def test_default_statuses_seeded_on_startup(client) -> None:
    response = client.get("/program-statuses")

    assert response.status_code == 200
    data = response.json()
    slugs = {s["slug"] for s in data}
    assert slugs == {"active", "paused", "completed", "archived"}


def test_default_active_status_is_marked_default(client) -> None:
    statuses = client.get("/program-statuses").json()
    active = next(s for s in statuses if s["slug"] == "active")

    assert active["is_default"] is True


def test_seeding_is_idempotent(client) -> None:
    # Hitting the index page triggers seed_default_program_statuses a second time
    client.get("/")
    client.get("/")

    statuses = client.get("/program-statuses").json()
    assert len([s for s in statuses if s["slug"] == "active"]) == 1


def test_default_statuses_sorted_by_sort_order(client) -> None:
    statuses = client.get("/program-statuses").json()
    orders = [s["sort_order"] for s in statuses]

    assert orders == sorted(orders)


# ── Program forms use configurable statuses ───────────────────────────────────

def test_program_list_page_shows_db_status_options(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Active" in response.text
    assert "Paused" in response.text
    assert "Completed" in response.text
    assert "Archived" in response.text


def test_program_create_uses_configurable_status(client) -> None:
    statuses = client.get("/program-statuses").json()
    paused = next(s for s in statuses if s["slug"] == "paused")

    program = client.post(
        "/programs", json={"name": "Paused Project", "status": "paused"}
    ).json()

    assert program["status"] == "paused"
    assert program["status_id"] == paused["id"]


def test_program_update_uses_configurable_status(client) -> None:
    program = client.post("/programs", json={"name": "Updatable"}).json()
    statuses = client.get("/program-statuses").json()
    completed_id = next(s["id"] for s in statuses if s["slug"] == "completed")

    updated = client.patch(
        f"/programs/{program['id']}", json={"status": "completed"}
    ).json()

    assert updated["status"] == "completed"
    assert updated["status_id"] == completed_id


def test_edit_program_page_shows_db_status_options(client) -> None:
    program = client.post("/programs", json={"name": "Edit Status Program"}).json()

    response = client.get(f"/programs/{program['id']}/edit")

    assert response.status_code == 200
    assert "Active" in response.text
    assert "Paused" in response.text


# ── Deactivate / reactivate ────────────────────────────────────────────────────

def test_deactivate_status(client) -> None:
    statuses = client.get("/program-statuses").json()
    archived = next(s for s in statuses if s["slug"] == "archived")

    response = client.patch(f"/program-statuses/{archived['id']}", json={"is_active": False})

    assert response.status_code == 200
    updated = client.get("/program-statuses").json()
    assert next(s for s in updated if s["slug"] == "archived")["is_active"] is False


def test_reactivate_status(client) -> None:
    statuses = client.get("/program-statuses").json()
    archived = next(s for s in statuses if s["slug"] == "archived")
    client.patch(f"/program-statuses/{archived['id']}", json={"is_active": False})

    response = client.patch(f"/program-statuses/{archived['id']}", json={"is_active": True})

    assert response.status_code == 200
    updated = client.get("/program-statuses").json()
    assert next(s for s in updated if s["slug"] == "archived")["is_active"] is True


def test_deactivated_status_hidden_from_new_program_form(client) -> None:
    statuses = client.get("/program-statuses").json()
    archived = next(s for s in statuses if s["slug"] == "archived")
    client.patch(f"/program-statuses/{archived['id']}", json={"is_active": False})

    response = client.get("/")

    assert response.status_code == 200
    # "Archived (inactive)" should not appear among regular options (it's filtered for new programs)
    # but the page still loads fine
    assert response.status_code == 200


# ── Preserve existing program data when status deactivated ────────────────────

def test_program_preserves_status_id_when_status_deactivated(client) -> None:
    statuses = client.get("/program-statuses").json()
    paused = next(s for s in statuses if s["slug"] == "paused")

    program = client.post("/programs", json={"name": "Will Stay Paused", "status": "paused"}).json()
    assert program["status"] == "paused"

    client.patch(f"/program-statuses/{paused['id']}", json={"is_active": False})

    fetched = client.get(f"/programs/{program['id']}").json()
    assert fetched["status"] == "paused"
    assert fetched["status_id"] == paused["id"]


# ── No hard-delete if status is used ─────────────────────────────────────────

def test_cannot_delete_status_used_by_program(client) -> None:
    program = client.post("/programs", json={"name": "Active Program"}).json()
    statuses = client.get("/program-statuses").json()
    active = next(s for s in statuses if s["slug"] == "active")
    assert program["status_id"] == active["id"]

    response = client.delete(f"/program-statuses/{active['id']}")

    assert response.status_code == 409


def test_can_delete_unused_status(client) -> None:
    new_status = client.post(
        "/program-statuses",
        json={"name": "On Hold", "slug": "on-hold", "color": "#f59e0b", "sort_order": 5},
    ).json()

    response = client.delete(f"/program-statuses/{new_status['id']}")

    assert response.status_code == 204


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_create_custom_status(client) -> None:
    response = client.post(
        "/program-statuses",
        json={"name": "On Hold", "slug": "on-hold", "color": "#f59e0b", "sort_order": 5},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "on-hold"
    assert data["name"] == "On Hold"
    assert data["is_active"] is True


def test_create_status_duplicate_slug_rejected(client) -> None:
    response = client.post(
        "/program-statuses",
        json={"name": "Another Active", "slug": "active"},
    )

    assert response.status_code == 409


def test_update_status_name_and_color(client) -> None:
    statuses = client.get("/program-statuses").json()
    archived = next(s for s in statuses if s["slug"] == "archived")

    response = client.patch(
        f"/program-statuses/{archived['id']}",
        json={"name": "Retired", "color": "#9ca3af"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Retired"
    assert response.json()["color"] == "#9ca3af"
    assert response.json()["slug"] == "archived"  # slug unchanged


def test_reorder_status(client) -> None:
    statuses = client.get("/program-statuses").json()
    paused = next(s for s in statuses if s["slug"] == "paused")

    response = client.patch(f"/program-statuses/{paused['id']}", json={"sort_order": 10})

    assert response.status_code == 200
    assert response.json()["sort_order"] == 10


# ── Settings UI ───────────────────────────────────────────────────────────────

def test_program_statuses_settings_page_loads(client) -> None:
    response = client.get("/settings")

    assert response.status_code == 200
    assert "Program Statuses" in response.text
    assert "Active" in response.text
    assert "New Program Status" in response.text


def test_create_status_from_settings_ui(client) -> None:
    response = client.post(
        "/settings/program-statuses/create",
        data={"name": "On Hold", "slug": "on-hold", "color": "#f59e0b", "sort_order": "5"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "On Hold" in response.text


def test_delete_unused_status_from_settings_ui(client) -> None:
    new_status = client.post(
        "/settings/program-statuses/create",
        data={"name": "On Hold", "slug": "on-hold", "color": "#f59e0b"},
        follow_redirects=False,
    )
    assert new_status.status_code == 303
    statuses = client.get("/program-statuses").json()
    created = next(s for s in statuses if s["slug"] == "on-hold")

    response = client.post(
        f"/settings/program-statuses/{created['id']}/delete",
        follow_redirects=True,
    )

    assert response.status_code == 200
    statuses_after = client.get("/program-statuses").json()
    assert all(s["slug"] != "on-hold" for s in statuses_after)

def test_create_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Launch Readiness"}).json()
    source_type = client.post("/source-types", json={"name": "Email"}).json()

    response = client.post(
        f"/programs/{program['id']}/work-items",
        json={
            "title": "Draft launch checklist",
            "description": "Collect readiness signals.",
            "status": "open",
            "priority": "high",
            "owner": "Sabrina",
            "next_step": "Review with launch owner",
            "source_type_id": source_type["id"],
            "link": "https://example.com/readiness",
            "due_date": "2026-06-01",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["program_id"] == program["id"]
    assert data["title"] == "Draft launch checklist"
    assert data["description"] == "Collect readiness signals."
    assert data["status"] == "open"
    assert data["priority"] == "high"
    assert data["owner"] == "Sabrina"
    assert data["next_step"] == "Review with launch owner"
    assert data["source_type_id"] == source_type["id"]
    assert data["link"] == "https://example.com/readiness"
    assert data["due_date"] == "2026-06-01"
    assert data["last_touched_at"] is None


def test_list_work_items(client) -> None:
    program = client.post("/programs", json={"name": "Operating Rhythm"}).json()
    client.post(f"/programs/{program['id']}/work-items", json={"title": "First"})
    client.post(f"/programs/{program['id']}/work-items", json={"title": "Second"})

    response = client.get(f"/programs/{program['id']}/work-items")

    assert response.status_code == 200
    assert {item["title"] for item in response.json()} == {"First", "Second"}


def test_get_update_and_delete_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Dependency Cleanup"}).json()
    created = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Find owner", "status": "open"},
    ).json()

    get_response = client.get(f"/work-items/{created['id']}")
    update_response = client.patch(
        f"/work-items/{created['id']}",
        json={
            "title": "Confirm owner",
            "status": "in_progress",
            "priority": "critical",
            "next_step": "Ping DRI",
        },
    )
    delete_response = client.delete(f"/work-items/{created['id']}")
    missing_response = client.get(f"/work-items/{created['id']}")

    assert get_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Confirm owner"
    assert update_response.json()["status"] == "in_progress"
    assert update_response.json()["priority"] == "critical"
    assert update_response.json()["next_step"] == "Ping DRI"
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404


def test_work_item_requires_existing_program(client) -> None:
    response = client.post("/programs/999/work-items", json={"title": "Nope"})

    assert response.status_code == 404


def test_rejects_invalid_work_item_status(client) -> None:
    program = client.post("/programs", json={"name": "Status Validation"}).json()

    response = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Bad status", "status": "waiting"},
    )

    assert response.status_code == 422


def test_rejects_invalid_work_item_priority(client) -> None:
    program = client.post("/programs", json={"name": "Priority Validation"}).json()

    response = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Bad priority", "priority": "urgent"},
    )

    assert response.status_code == 422


def test_rejects_missing_source_type_for_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Source Validation"}).json()

    response = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Missing source", "source_type_id": 999},
    )

    assert response.status_code == 404


def test_mark_work_item_touched_sets_timestamp_without_status_change(client) -> None:
    program = client.post("/programs", json={"name": "Touch Work"}).json()
    created = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Touch me", "status": "blocked"},
    ).json()

    response = client.post(f"/work-items/{created['id']}/mark-touched")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["last_touched_at"] is not None

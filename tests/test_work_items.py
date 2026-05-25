def test_create_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Launch Readiness"}).json()

    response = client.post(
        f"/programs/{program['id']}/work-items",
        json={
            "title": "Draft launch checklist",
            "description": "Collect readiness signals.",
            "status": "open",
            "owner": "Sabrina",
            "due_date": "2026-06-01",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["program_id"] == program["id"]
    assert data["title"] == "Draft launch checklist"
    assert data["description"] == "Collect readiness signals."
    assert data["status"] == "open"
    assert data["owner"] == "Sabrina"
    assert data["due_date"] == "2026-06-01"


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
        json={"title": "Confirm owner", "status": "in_progress"},
    )
    delete_response = client.delete(f"/work-items/{created['id']}")
    missing_response = client.get(f"/work-items/{created['id']}")

    assert get_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Confirm owner"
    assert update_response.json()["status"] == "in_progress"
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

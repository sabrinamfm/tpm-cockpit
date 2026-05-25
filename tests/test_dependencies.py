def test_create_dependency(client) -> None:
    program = client.post("/programs", json={"name": "Dependency Program"}).json()

    response = client.post(
        f"/programs/{program['id']}/dependencies",
        json={
            "title": "Security approval",
            "description": "Needs review before launch.",
            "dependency_type": "security",
            "owner": "Ada",
            "external_team": "Security",
            "status": "open",
            "blocking_level": "high",
            "due_date": "2026-06-01",
            "notes": "Asked in review channel.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["program_id"] == program["id"]
    assert data["title"] == "Security approval"
    assert data["dependency_type"] == "security"
    assert data["owner"] == "Ada"
    assert data["external_team"] == "Security"
    assert data["blocking_level"] == "high"
    assert data["due_date"] == "2026-06-01"
    assert data["last_confirmation_at"] is None


def test_list_dependencies(client) -> None:
    program = client.post("/programs", json={"name": "Dependency List"}).json()
    client.post(f"/programs/{program['id']}/dependencies", json={"title": "First"})
    client.post(f"/programs/{program['id']}/dependencies", json={"title": "Second"})

    response = client.get(f"/programs/{program['id']}/dependencies")

    assert response.status_code == 200
    assert {item["title"] for item in response.json()} == {"First", "Second"}


def test_get_update_confirm_and_delete_dependency(client) -> None:
    program = client.post("/programs", json={"name": "Dependency CRUD"}).json()
    created = client.post(
        f"/programs/{program['id']}/dependencies",
        json={"title": "Approval", "dependency_type": "approval"},
    ).json()

    get_response = client.get(f"/dependencies/{created['id']}")
    update_response = client.patch(
        f"/dependencies/{created['id']}",
        json={"title": "Approval confirmed", "status": "in_progress", "blocking_level": "critical"},
    )
    confirm_response = client.post(f"/dependencies/{created['id']}/confirm")
    delete_response = client.delete(f"/dependencies/{created['id']}")
    missing_response = client.get(f"/dependencies/{created['id']}")

    assert get_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Approval confirmed"
    assert update_response.json()["status"] == "in_progress"
    assert update_response.json()["blocking_level"] == "critical"
    assert confirm_response.status_code == 200
    assert confirm_response.json()["last_confirmation_at"] is not None
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404


def test_dependency_requires_existing_program(client) -> None:
    response = client.post("/programs/999/dependencies", json={"title": "Nope"})

    assert response.status_code == 404


def test_rejects_invalid_dependency_values(client) -> None:
    program = client.post("/programs", json={"name": "Dependency Validation"}).json()

    response = client.post(
        f"/programs/{program['id']}/dependencies",
        json={"title": "Bad values", "dependency_type": "person", "blocking_level": "urgent"},
    )

    assert response.status_code == 422

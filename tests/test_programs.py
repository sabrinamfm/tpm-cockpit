def test_create_program(client) -> None:
    response = client.post(
        "/programs",
        json={
            "name": "Customer Launch",
            "description": "Coordinate launch readiness.",
            "status": "active",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Customer Launch"
    assert data["description"] == "Coordinate launch readiness."
    assert data["status"] == "active"
    assert data["created_at"]
    assert data["updated_at"]


def test_list_programs(client) -> None:
    client.post("/programs", json={"name": "First", "status": "active"})
    client.post("/programs", json={"name": "Second", "status": "paused"})

    response = client.get("/programs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {program["name"] for program in data} == {"First", "Second"}


def test_get_program(client) -> None:
    created = client.post("/programs", json={"name": "Portfolio Sync"}).json()

    response = client.get(f"/programs/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == "Portfolio Sync"


def test_get_missing_program_returns_404(client) -> None:
    response = client.get("/programs/999")

    assert response.status_code == 404


def test_update_program(client) -> None:
    created = client.post(
        "/programs",
        json={"name": "Old Name", "description": "Old description", "status": "active"},
    ).json()

    response = client.patch(
        f"/programs/{created['id']}",
        json={"name": "New Name", "status": "completed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["description"] == "Old description"
    assert data["status"] == "completed"


def test_delete_program(client) -> None:
    created = client.post("/programs", json={"name": "Temporary Program"}).json()

    delete_response = client.delete(f"/programs/{created['id']}")
    get_response = client.get(f"/programs/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_rejects_invalid_program_status(client) -> None:
    # "blocked" is a work-item status slug, not a program status slug
    response = client.post("/programs", json={"name": "Bad Status", "status": "blocked"})

    assert response.status_code == 422

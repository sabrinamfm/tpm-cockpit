def test_create_and_list_source_types(client) -> None:
    create_response = client.post("/source-types", json={"name": "Email"})
    list_response = client.get("/source-types")

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Email"
    assert create_response.json()["is_active"] is True
    assert list_response.status_code == 200
    assert [source_type["name"] for source_type in list_response.json()] == ["Email"]


def test_deactivate_and_reactivate_source_type(client) -> None:
    source_type = client.post("/source-types", json={"name": "Jira ticket"}).json()

    deactivate_response = client.patch(
        f"/source-types/{source_type['id']}",
        json={"is_active": False},
    )
    reactivate_response = client.patch(
        f"/source-types/{source_type['id']}",
        json={"is_active": True},
    )

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True


def test_create_source_type_from_settings_ui(client) -> None:
    response = client.post(
        "/settings/source-types/create",
        data={"name": "Meeting", "slug": "meeting"},
        follow_redirects=False,
    )
    created = client.get("/source-types").json()[0]

    assert response.status_code == 303
    assert created["name"] == "Meeting"
    assert created["slug"] == "meeting"

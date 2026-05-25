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


def test_source_type_settings_page_can_toggle_activation(client) -> None:
    client.post("/settings/source-types/create", data={"name": "Meeting"})
    created = client.get("/source-types").json()[0]

    deactivate_response = client.post(
        f"/settings/source-types/{created['id']}/deactivate",
        follow_redirects=False,
    )
    deactivated = client.get("/source-types").json()[0]
    reactivate_response = client.post(
        f"/settings/source-types/{created['id']}/activate",
        follow_redirects=False,
    )
    reactivated = client.get("/source-types").json()[0]

    assert deactivate_response.status_code == 303
    assert deactivated["is_active"] is False
    assert reactivate_response.status_code == 303
    assert reactivated["is_active"] is True

def test_program_ui_loads(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "TPM Cockpit" in response.text
    assert "Program List" in response.text
    assert "Attention" in response.text
    assert "All statuses" in response.text
    assert "All attention states" in response.text


def test_program_ui_links_to_detail_page(client) -> None:
    created = client.post(
        "/programs",
        json={"name": "Executive Reporting", "description": "Weekly readout"},
    ).json()

    list_response = client.get("/")
    detail_response = client.get(f"/programs/{created['id']}/view")

    assert list_response.status_code == 200
    assert f"/programs/{created['id']}/view" in list_response.text
    assert detail_response.status_code == 200
    assert "Executive Reporting" in detail_response.text
    assert "Weekly readout" in detail_response.text
    assert "Work Items" in detail_response.text
    assert "Risks" in detail_response.text
    assert "Dependencies" in detail_response.text
    assert "Decisions" in detail_response.text
    assert "Notes" in detail_response.text


def test_program_ui_filters_by_status(client) -> None:
    client.post("/programs", json={"name": "Active Program", "status": "active"})
    client.post("/programs", json={"name": "Paused Program", "status": "paused"})

    response = client.get("/?status_filter=paused")

    assert response.status_code == 200
    assert "Paused Program" in response.text
    assert "Active Program" not in response.text


def test_program_detail_page_shows_work_items_grouped_by_status(client) -> None:
    program = client.post("/programs", json={"name": "Program With Work"}).json()
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Open item", "status": "open"},
    )
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Blocked item", "status": "blocked"},
    )

    response = client.get(f"/programs/{program['id']}/view")

    assert response.status_code == 200
    assert "Open" in response.text
    assert "Blocked" in response.text
    assert "Open item" in response.text
    assert "Blocked item" in response.text
    assert "Create Work Item" in response.text


def test_program_list_shows_attention_from_blocked_work_item(client) -> None:
    program = client.post("/programs", json={"name": "Needs Follow Up"}).json()
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Blocked item", "status": "blocked"},
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Needs Follow Up" in response.text
    assert "Needs attention" in response.text

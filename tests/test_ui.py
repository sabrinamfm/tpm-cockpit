def test_program_ui_loads(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "TPM Cockpit" in response.text
    assert "Program List" in response.text
    assert "Attention" in response.text
    assert "All statuses" in response.text
    assert "All attention states" in response.text
    assert "Actions" in response.text


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


def test_program_delete_requires_confirmation_page(client) -> None:
    program = client.post("/programs", json={"name": "Confirm Me"}).json()

    list_response = client.get("/")
    confirm_response = client.get(f"/programs/{program['id']}/delete/confirm")

    assert list_response.status_code == 200
    assert f"/programs/{program['id']}/delete/confirm" in list_response.text
    assert confirm_response.status_code == 200
    assert "Confirm Delete" in confirm_response.text


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
    assert "<th>Title</th>" in response.text
    assert "<th>Priority</th>" in response.text
    assert "<th>Next Step</th>" in response.text
    assert "<th>Source Type</th>" in response.text
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


def test_work_item_ui_filters_by_owner_and_source_type(client) -> None:
    program = client.post("/programs", json={"name": "Filter Work"}).json()
    email = client.post("/source-types", json={"name": "Email"}).json()
    meeting = client.post("/source-types", json={"name": "Meeting"}).json()
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Email item", "owner": "Sabrina", "source_type_id": email["id"]},
    )
    client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Meeting item", "owner": "Ada", "source_type_id": meeting["id"]},
    )

    response = client.get(
        f"/programs/{program['id']}/view?owner_filter=Sabrina&source_type_filter={email['id']}"
    )

    assert response.status_code == 200
    assert "Email item" in response.text
    assert "Meeting item" not in response.text


def test_work_item_ui_sort_control_and_delete_confirmation(client) -> None:
    program = client.post("/programs", json={"name": "Sort Work"}).json()
    work_item = client.post(
        f"/programs/{program['id']}/work-items",
        json={
            "title": "Sortable item",
            "priority": "critical",
            "next_step": "Follow up today",
            "link": "https://example.com/source",
        },
    ).json()

    detail_response = client.get(f"/programs/{program['id']}/view?work_sort=priority&priority_filter=critical")
    confirm_response = client.get(f"/work-items/{work_item['id']}/delete/confirm")

    assert detail_response.status_code == 200
    assert "Sortable item" in detail_response.text
    assert "critical" in detail_response.text
    assert "Follow up today" in detail_response.text
    assert "Stale" in detail_response.text
    assert "https://example.com/source" in detail_response.text
    assert f"/work-items/{work_item['id']}/touch" in detail_response.text
    assert f"/work-items/{work_item['id']}/delete/confirm" in detail_response.text
    assert confirm_response.status_code == 200
    assert "Confirm Delete" in confirm_response.text


def test_mark_touched_from_ui_redirects_to_program(client) -> None:
    program = client.post("/programs", json={"name": "Touch UI"}).json()
    work_item = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Touch from UI"},
    ).json()

    response = client.post(f"/work-items/{work_item['id']}/touch", follow_redirects=False)
    touched = client.get(f"/work-items/{work_item['id']}").json()

    assert response.status_code == 303
    assert response.headers["location"] == f"/programs/{program['id']}/view"
    assert touched["last_touched_at"] is not None

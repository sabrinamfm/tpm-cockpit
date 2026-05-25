def test_program_ui_loads(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "TPM Cockpit" in response.text
    assert "Program List" in response.text

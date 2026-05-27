"""Tests for the Status Report detail/edit view."""


def _make_program_with_report(client, *, reported_health="on_track"):
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": reported_health},
    ).json()
    return prog, report


# ── View page ─────────────────────────────────────────────────────────────────

def test_status_report_detail_renders(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200


def test_status_report_detail_shows_metadata(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "2026-05-26" in resp.text
    assert "On Track" in resp.text
    assert report["report_title"] in resp.text


def test_status_report_detail_shows_report_title(client) -> None:
    prog = client.post("/programs", json={"name": "Orion"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()
    assert report["report_title"] == "Week 22 Orion Report"
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "Week 22 Orion Report" in resp.text


def test_status_report_detail_shows_summary(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track", "summary": "All is well."},
    ).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "All is well." in resp.text


def test_status_report_detail_not_found(client) -> None:
    assert client.get("/status-reports/99999/view").status_code == 404


def test_status_report_detail_links_back_to_program(client) -> None:
    prog, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert f"/programs/{prog['id']}/view" in resp.text


def test_status_report_detail_has_no_standalone_edit_form(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert 'id="edit-report"' not in resp.text


def test_status_report_detail_divergence_shown(client) -> None:
    # An empty program computes on_track; reporting off_track creates a divergence.
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "off_track"},
    ).json()
    assert report["reported_health"] != report["suggested_health"]
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "differs" in resp.text


# ── Create redirect ───────────────────────────────────────────────────────────

def test_status_report_create_redirects_to_detail(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/status-reports/create",
        data={"report_date": "2026-05-26", "reported_health": "on_track"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/status-reports/")
    assert resp.headers["location"].endswith("/view")


def test_status_report_create_redirect_page_shows_report(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    resp = client.post(
        f"/programs/{prog['id']}/status-reports/create",
        data={"report_date": "2026-05-26", "reported_health": "at_risk", "summary": "Looking good."},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "2026-05-26" in resp.text
    assert "At Risk" in resp.text
    assert "Looking good." in resp.text


# ── Update redirect ───────────────────────────────────────────────────────────

def test_status_report_update_from_detail_redirects_to_detail(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.post(
        f"/status-reports/{report['id']}/update",
        data={"report_date": "2026-05-26", "reported_health": "at_risk", "return_to": "detail"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_status_report_update_from_program_redirects_to_program(client) -> None:
    prog, report = _make_program_with_report(client)
    resp = client.post(
        f"/status-reports/{report['id']}/update",
        data={"report_date": "2026-05-26", "reported_health": "at_risk"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"


# ── Recalculate health ────────────────────────────────────────────────────────

def test_status_report_recalculate_health(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()
    resp = client.post(f"/status-reports/{report['id']}/recalculate-health", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"
    updated = client.get(f"/status-reports/{report['id']}").json()
    assert updated["suggested_health"] in ("on_track", "at_risk", "off_track")


def test_status_report_recalculate_health_not_found(client) -> None:
    resp = client.post("/status-reports/99999/recalculate-health", follow_redirects=False)
    assert resp.status_code == 404


def test_recalculate_does_not_change_reported_health(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "off_track"},
    ).json()
    client.post(f"/status-reports/{report['id']}/recalculate-health", follow_redirects=False)
    updated = client.get(f"/status-reports/{report['id']}").json()
    assert updated["reported_health"] == "off_track"


def test_suggested_health_not_changed_on_normal_edit(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    report = client.post(
        f"/programs/{prog['id']}/status-reports",
        json={"report_date": "2026-05-26", "reported_health": "on_track"},
    ).json()
    original_suggested = report["suggested_health"]
    client.post(
        f"/status-reports/{report['id']}/update",
        data={"report_date": "2026-05-27", "reported_health": "at_risk", "return_to": "detail"},
        follow_redirects=False,
    )
    updated = client.get(f"/status-reports/{report['id']}").json()
    assert updated["suggested_health"] == original_suggested


# ── Links from list/program views ─────────────────────────────────────────────

def test_program_detail_report_date_links_to_detail(client) -> None:
    prog, report = _make_program_with_report(client)
    resp = client.get(f"/programs/{prog['id']}/view")
    assert resp.status_code == 200
    assert f"/status-reports/{report['id']}/view" in resp.text


def test_index_page_report_pill_links_to_detail(client) -> None:
    prog, report = _make_program_with_report(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert f"/status-reports/{report['id']}/view" in resp.text


# ── Operational context ───────────────────────────────────────────────────────

def test_status_report_detail_shows_operational_context_sections(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "Operational Context" in resp.text
    assert "Milestones" in resp.text
    assert "Requirements" in resp.text
    assert "Features" in resp.text
    assert "Dependencies" in resp.text
    assert "Risks" in resp.text
    assert "Open Decisions" in resp.text
    assert "Work Items" not in resp.text


def test_status_report_detail_shows_active_risk(client) -> None:
    prog, report = _make_program_with_report(client)
    client.post(f"/programs/{prog['id']}/risks", json={"title": "Data breach risk", "status": "open", "likelihood": "likely", "severity": "high"})
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "Data breach risk" in resp.text


def test_status_report_detail_does_not_show_resolved_risk(client) -> None:
    prog, report = _make_program_with_report(client)
    client.post(f"/programs/{prog['id']}/risks", json={"title": "Old risk", "status": "resolved", "likelihood": "unlikely", "severity": "low"})
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "Old risk" not in resp.text


# ── Edit links in operational context ────────────────────────────────────────

def _report_edit_url(prog_id, item_type, item_id, report_id):
    return f"/programs/{prog_id}/view?edit_{item_type}_id={item_id}&return_to=/status-reports/{report_id}/view"


def test_status_report_detail_edit_link_milestone(client) -> None:
    prog, report = _make_program_with_report(client)
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1", "status": "on_track"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "milestone", ms["id"], report["id"]) in resp.text


def test_status_report_detail_edit_link_requirement(client) -> None:
    prog, report = _make_program_with_report(client)
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R1", "status": "in_progress"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "requirement", req["id"], report["id"]) in resp.text


def test_status_report_detail_edit_link_feature(client) -> None:
    prog, report = _make_program_with_report(client)
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F1", "status": "in_progress"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "feature", ft["id"], report["id"]) in resp.text


def test_status_report_detail_edit_link_dependency(client) -> None:
    prog, report = _make_program_with_report(client)
    dep = client.post(f"/programs/{prog['id']}/dependencies", json={"title": "D1", "status": "blocked", "blocking_level": "high"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "dependency", dep["id"], report["id"]) in resp.text


def test_status_report_detail_edit_link_risk(client) -> None:
    prog, report = _make_program_with_report(client)
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "Risk1", "status": "open"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "risk", risk["id"], report["id"]) in resp.text


def test_status_report_detail_edit_link_decision(client) -> None:
    prog, report = _make_program_with_report(client)
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "Dec1", "status": "proposed"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert _report_edit_url(prog["id"], "decision", dec["id"], report["id"]) in resp.text


# ── return_to redirects after editing operational context items ───────────────

def test_update_milestone_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1", "status": "on_track"}).json()
    resp = client.post(
        f"/milestones/{ms['id']}/update",
        data={"title": "M1 Updated", "status": "achieved", "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_update_requirement_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    req = client.post(f"/programs/{prog['id']}/requirements", json={"title": "R1"}).json()
    resp = client.post(
        f"/requirements/{req['id']}/update",
        data={"title": "R1 Updated", "status": "delivered", "source_type": "okr",
              "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_update_feature_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    ft = client.post(f"/programs/{prog['id']}/features", json={"title": "F1"}).json()
    resp = client.post(
        f"/features/{ft['id']}/update",
        data={"title": "F1 Updated", "status": "delivered",
              "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_update_dependency_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    dep = client.post(f"/programs/{prog['id']}/dependencies", json={"title": "D1", "blocking_level": "medium"}).json()
    resp = client.post(
        f"/dependencies/{dep['id']}/update",
        data={"title": "D1 Updated", "status": "resolved", "blocking_level": "medium",
              "dependency_type": dep["dependency_type"],
              "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_update_risk_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    risk = client.post(f"/programs/{prog['id']}/risks", json={"title": "Risk1"}).json()
    resp = client.post(
        f"/risks/{risk['id']}/update",
        data={"title": "Risk1 Updated", "status": "mitigated",
              "severity": risk["severity"], "likelihood": risk["likelihood"],
              "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


def test_update_decision_returns_to_report(client) -> None:
    prog, report = _make_program_with_report(client)
    dec = client.post(f"/programs/{prog['id']}/decisions", json={"title": "Dec1"}).json()
    resp = client.post(
        f"/decisions/{dec['id']}/update",
        data={"title": "Dec1 Updated", "status": "decided",
              "return_to": f"/status-reports/{report['id']}/view"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/status-reports/{report['id']}/view"


# ── Program detail edit still redirects to program when no return_to ─────────

def test_update_milestone_without_return_to_stays_on_program(client) -> None:
    prog = client.post("/programs", json={"name": "P"}).json()
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1", "status": "on_track"}).json()
    resp = client.post(
        f"/milestones/{ms['id']}/update",
        data={"title": "M1 Updated", "status": "achieved"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/programs/{prog['id']}/view"

# ── Milestone timeline ────────────────────────────────────────────────────────

def test_milestone_timeline_renders(client) -> None:
    prog, report = _make_program_with_report(client)
    client.post(f"/programs/{prog['id']}/milestones", json={"title": "Launch", "status": "on_track", "target_date": "2026-09-01"})
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "ms-timeline" in resp.text
    assert "Launch" in resp.text


def test_milestone_timeline_shows_all_statuses(client) -> None:
    prog, report = _make_program_with_report(client)
    for title, status in [("Planned MS", "planned"), ("Achieved MS", "achieved"), ("Cancelled MS", "cancelled")]:
        client.post(f"/programs/{prog['id']}/milestones", json={"title": title, "status": status})
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "Planned MS" in resp.text
    assert "Achieved MS" in resp.text
    assert "Cancelled MS" in resp.text


def test_milestone_timeline_card_links_to_edit(client) -> None:
    prog, report = _make_program_with_report(client)
    ms = client.post(f"/programs/{prog['id']}/milestones", json={"title": "M1", "status": "on_track"}).json()
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert f"edit_milestone_id={ms['id']}" in resp.text
    assert f"return_to=/status-reports/{report['id']}/view" in resp.text


def test_milestone_timeline_chronological_order(client) -> None:
    prog, report = _make_program_with_report(client)
    client.post(f"/programs/{prog['id']}/milestones", json={"title": "Later", "status": "planned", "target_date": "2026-12-01"})
    client.post(f"/programs/{prog['id']}/milestones", json={"title": "Earlier", "status": "planned", "target_date": "2026-07-01"})
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    earlier_pos = resp.text.index("Earlier")
    later_pos = resp.text.index("Later")
    assert earlier_pos < later_pos


def test_milestone_timeline_empty_state(client) -> None:
    _, report = _make_program_with_report(client)
    resp = client.get(f"/status-reports/{report['id']}/view")
    assert resp.status_code == 200
    assert "No milestones yet." in resp.text

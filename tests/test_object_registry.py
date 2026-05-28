"""Tests for the canonical object registry in app/domain/object_registry.py."""

import pytest

from app.domain.object_registry import OBJECT_REGISTRY, VALID_OBJECT_TYPES, lookup_object
from app.models import Decision, Dependency, Feature, Milestone, Requirement, Risk, WorkItem
from app.models.status_report import StatusReport


EXPECTED_TYPES = {
    "work_item",
    "dependency",
    "risk",
    "status_report",
    "milestone",
    "decision",
    "requirement",
    "feature",
}

EXPECTED_MODELS = {
    "work_item": WorkItem,
    "dependency": Dependency,
    "risk": Risk,
    "status_report": StatusReport,
    "milestone": Milestone,
    "decision": Decision,
    "requirement": Requirement,
    "feature": Feature,
}


# ── Registry completeness ─────────────────────────────────────────────────────

def test_registry_contains_all_expected_types() -> None:
    assert set(OBJECT_REGISTRY.keys()) == EXPECTED_TYPES


def test_registry_maps_to_correct_models() -> None:
    for type_str, expected_model in EXPECTED_MODELS.items():
        assert OBJECT_REGISTRY[type_str] is expected_model, (
            f"OBJECT_REGISTRY['{type_str}'] should be {expected_model.__name__}"
        )


def test_valid_object_types_matches_registry_keys() -> None:
    assert VALID_OBJECT_TYPES == frozenset(OBJECT_REGISTRY.keys())


def test_registry_has_no_extra_types() -> None:
    assert set(OBJECT_REGISTRY.keys()) - EXPECTED_TYPES == set()


# ── lookup_object ─────────────────────────────────────────────────────────────

def test_lookup_object_returns_none_for_unknown_type(client) -> None:
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        result = lookup_object(db, "not_a_real_type", 1)
    assert result is None


def test_lookup_object_returns_none_for_missing_id(client) -> None:
    program = client.post("/programs", json={"name": "Registry Test"}).json()
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        result = lookup_object(db, "work_item", 99999)
    assert result is None


def test_lookup_object_returns_instance_for_existing_object(client) -> None:
    program = client.post("/programs", json={"name": "Registry Lookup"}).json()
    wi = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Lookup target", "status": "open"},
    ).json()
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        result = lookup_object(db, "work_item", wi["id"])
    assert result is not None
    assert result.id == wi["id"]


# ── Route integration: relationships.py uses registry ────────────────────────

def test_create_relationship_resolves_objects_via_registry(client) -> None:
    program = client.post("/programs", json={"name": "Registry Rel"}).json()
    wi = client.post(
        f"/programs/{program['id']}/work-items",
        json={"title": "Source", "status": "open"},
    ).json()
    dep = client.post(
        f"/programs/{program['id']}/dependencies",
        json={"title": "Target", "status": "open", "blocking_level": "medium"},
    ).json()

    response = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": wi["id"],
        "relationship_type": "blocks",
        "target_type": "dependency",
        "target_id": dep["id"],
    })

    assert response.status_code == 201


def test_create_relationship_404_for_nonexistent_object(client) -> None:
    response = client.post("/relationships", json={
        "source_type": "work_item",
        "source_id": 99999,
        "relationship_type": "relates_to",
        "target_type": "risk",
        "target_id": 99999,
    })
    assert response.status_code == 404


# ── Route integration: ui.py uses registry ───────────────────────────────────

def test_ui_create_relationship_resolves_objects_via_registry(client) -> None:
    program = client.post("/programs", json={"name": "UI Registry"}).json()
    ms = client.post(
        f"/programs/{program['id']}/milestones",
        json={"title": "MS", "status": "planned"},
    ).json()
    risk = client.post(
        f"/programs/{program['id']}/risks",
        json={"title": "R", "severity": "medium", "likelihood": "possible", "status": "open"},
    ).json()

    response = client.post(
        f"/programs/{program['id']}/relationships/create",
        data={
            "source_ref": f"milestone:{ms['id']}",
            "target_ref": f"risk:{risk['id']}",
            "relationship_type": "relates_to",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    rels = client.get(f"/programs/{program['id']}/relationships").json()
    assert len(rels) == 1


def test_ui_create_relationship_rejects_invalid_type(client) -> None:
    program = client.post("/programs", json={"name": "Bad Type"}).json()

    response = client.post(
        f"/programs/{program['id']}/relationships/create",
        data={
            "source_ref": "not_a_type:1",
            "target_ref": "also_bad:2",
            "relationship_type": "relates_to",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Invalid object type" in response.text


# ── No local maps remain in route files ──────────────────────────────────────

def test_relationships_route_has_no_local_object_map() -> None:
    import ast, pathlib
    src = pathlib.Path("app/api/routes/relationships.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "OBJECT_MODEL_MAP" in target.id:
                    pytest.fail(
                        f"Found local object map '{target.id}' in relationships.py — "
                        "it should import from app.domain.object_registry instead."
                    )


def test_ui_route_has_no_local_object_map() -> None:
    import ast, pathlib
    src = pathlib.Path("app/api/routes/ui.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and "OBJECT_MODEL_MAP" in target.id:
                    pytest.fail(
                        f"Found local object map '{target.id}' in ui.py — "
                        "it should import from app.domain.object_registry instead."
                    )

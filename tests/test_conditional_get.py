"""Tests for version-based ETags and conditional GET (304)."""

from fastapi.testclient import TestClient

from app import conditional

CARD_BODY = {
    "binder_id": 3,
    "name": "Gengar",
    "set_name": "Fossil",
    "collector_number": "5/62",
    "rarity": "Holo Rare",
}

CERT_BODY = {
    "card_id": 3,
    "grading_company": "PSA",
    "cert_number": "PSA-99999999",
    "grade": 9.5,
    "graded_at": "2024-08-01",
}


# --- ETag helpers ---


def test_etag_for_is_quoted_and_versioned() -> None:
    assert conditional.etag_for("card", 9, 4) == '"card-9-v4"'


def test_etag_for_children_changes_with_child_versions() -> None:
    first = conditional.etag_for_children("binder", 1, 2, [(1, 1), (2, 1)])
    same = conditional.etag_for_children("binder", 1, 2, [(1, 1), (2, 1)])
    changed = conditional.etag_for_children("binder", 1, 2, [(1, 2), (2, 1)])
    assert first == same
    assert first != changed


def test_if_none_match_uses_weak_comparison() -> None:
    assert conditional.if_none_match_matches('"a-1"', '"a-1"')
    assert conditional.if_none_match_matches('W/"a-1"', '"a-1"')
    assert conditional.if_none_match_matches('"x", "a-1"', '"a-1"')
    assert conditional.if_none_match_matches("*", '"a-1"')
    assert not conditional.if_none_match_matches('"b"', '"a-1"')
    assert not conditional.if_none_match_matches(None, '"a-1"')


def test_if_match_uses_strong_comparison() -> None:
    assert conditional.if_match_matches('"a-1"', '"a-1"')
    assert conditional.if_match_matches('"x", "a-1"', '"a-1"')
    assert conditional.if_match_matches("*", '"a-1"')
    assert not conditional.if_match_matches('W/"a-1"', '"a-1"')
    assert not conditional.if_match_matches('"b"', '"a-1"')
    assert not conditional.if_match_matches(None, '"a-1"')


# --- Conditional GET ---


def test_card_detail_returns_etag_and_cache_control(client: TestClient) -> None:
    response = client.get("/cards/1")
    assert response.status_code == 200
    assert response.headers["etag"] == '"card-1-v1"'
    assert response.headers["cache-control"] == "no-cache"


def test_matching_if_none_match_returns_304(client: TestClient) -> None:
    etag = client.get("/cards/1").headers["etag"]
    response = client.get("/cards/1", headers={"If-None-Match": etag})
    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == etag
    assert response.headers["cache-control"] == "no-cache"


def test_weak_if_none_match_returns_304(client: TestClient) -> None:
    etag = client.get("/cards/1").headers["etag"]
    response = client.get("/cards/1", headers={"If-None-Match": f"W/{etag}"})
    assert response.status_code == 304


def test_star_if_none_match_returns_304(client: TestClient) -> None:
    assert client.get("/cards/1", headers={"If-None-Match": "*"}).status_code == 304


def test_stale_if_none_match_returns_200(client: TestClient) -> None:
    response = client.get("/cards/1", headers={"If-None-Match": '"stale"'})
    assert response.status_code == 200
    assert response.json()["name"] == "Charizard"


def test_all_list_endpoints_support_304(client: TestClient) -> None:
    for path in ("/binders", "/cards", "/certificates", "/search?q=charizard"):
        etag = client.get(path).headers["etag"]
        response = client.get(path, headers={"If-None-Match": etag})
        assert response.status_code == 304, path


def test_unchanged_binder_detail_returns_304(client: TestClient) -> None:
    etag = client.get("/binders/1").headers["etag"]
    response = client.get("/binders/1", headers={"If-None-Match": etag})
    assert response.status_code == 304


def test_nested_card_change_invalidates_binder_detail(client: TestClient) -> None:
    etag = client.get("/binders/1").headers["etag"]
    client.put("/cards/1", json={"version": 1, "name": "Charizard (Base)"})
    response = client.get("/binders/1", headers={"If-None-Match": etag})
    assert response.status_code == 200
    assert response.headers["etag"] != etag


def test_certificate_attach_invalidates_card_detail(client: TestClient) -> None:
    etag = client.get("/cards/3").headers["etag"]
    assert client.post("/certificates", json=CERT_BODY).status_code == 201
    response = client.get("/cards/3", headers={"If-None-Match": etag})
    assert response.status_code == 200
    assert response.headers["etag"] != etag


def test_card_creation_invalidates_cards_list(client: TestClient) -> None:
    etag = client.get("/cards").headers["etag"]
    assert client.post("/cards", json=CARD_BODY).status_code == 201
    response = client.get("/cards", headers={"If-None-Match": etag})
    assert response.status_code == 200
    assert response.headers["etag"] != etag


def test_binder_rename_invalidates_search_results(client: TestClient) -> None:
    etag = client.get("/search", params={"q": "charizard"}).headers["etag"]
    client.put("/binders/1", json={"version": 1, "name": "Renamed Vault"})
    response = client.get(
        "/search", params={"q": "charizard"}, headers={"If-None-Match": etag}
    )
    assert response.status_code == 200


def test_non_get_requests_never_return_304(client: TestClient) -> None:
    etag = client.get("/cards/3").headers["etag"]
    response = client.put(
        "/cards/3",
        json={"version": 1, "name": "Blastoise (Base)"},
        headers={"If-None-Match": etag},
    )
    assert response.status_code == 200


def test_missing_resource_has_no_etag(client: TestClient) -> None:
    response = client.get("/cards/999")
    assert response.status_code == 404
    assert "etag" not in response.headers

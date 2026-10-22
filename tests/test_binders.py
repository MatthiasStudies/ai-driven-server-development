"""Integration tests for the binder endpoints."""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from fastapi.testclient import TestClient


def test_create_binder_returns_201(client: TestClient) -> None:
    response = client.post(
        "/binders", json={"name": "Trade Pad", "description": "Pad for trades"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Trade Pad"
    assert body["description"] == "Pad for trades"
    assert body["id"] > 3
    assert body["version"] == 1
    assert body["created_at"]


def test_create_binder_without_description(client: TestClient) -> None:
    response = client.post("/binders", json={"name": "No Description"})
    assert response.status_code == 201
    assert response.json()["description"] is None


def test_create_binder_validates_name(client: TestClient) -> None:
    assert client.post("/binders", json={"name": ""}).status_code == 422
    assert client.post("/binders", json={"name": "x" * 101}).status_code == 422
    assert client.post("/binders", json={}).status_code == 422


def test_list_binders_returns_seed_data(client: TestClient) -> None:
    response = client.get("/binders")
    assert response.status_code == 200
    assert [binder["name"] for binder in response.json()] == [
        "Vintage Vault",
        "Modern Alt Arts",
        "Trade Binder",
    ]


def test_list_binders_name_filter_is_substring_and_ci(client: TestClient) -> None:
    response = client.get("/binders", params={"name": "vault"})
    assert [binder["name"] for binder in response.json()] == ["Vintage Vault"]


def test_list_binders_order_by_name_desc(client: TestClient) -> None:
    response = client.get("/binders", params={"order_by": "name", "order": "desc"})
    assert [binder["name"] for binder in response.json()] == [
        "Vintage Vault",
        "Trade Binder",
        "Modern Alt Arts",
    ]


def test_list_binders_pagination(client: TestClient) -> None:
    response = client.get("/binders", params={"limit": 2, "offset": 1})
    assert [binder["name"] for binder in response.json()] == [
        "Modern Alt Arts",
        "Trade Binder",
    ]


def test_list_binders_rejects_unknown_order_by(client: TestClient) -> None:
    response = client.get("/binders", params={"order_by": "id"})
    assert response.status_code == 422


def test_get_binder_detail_includes_cards(client: TestClient) -> None:
    response = client.get("/binders/1")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Vintage Vault"
    assert [card["name"] for card in body["cards"]] == [
        "Charizard",
        "Lugia",
        "Blastoise",
    ]
    assert body["cards"][0]["certificate"]["grade"] == 9.0
    assert body["cards"][2]["certificate"] is None


def test_get_missing_binder_returns_404(client: TestClient) -> None:
    response = client.get("/binders/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Binder not found"


def _binder_etag(client: TestClient, binder_id: int) -> str:
    return client.get(f"/binders/{binder_id}").headers["etag"]


def test_update_binder_is_partial(client: TestClient) -> None:
    response = client.put(
        "/binders/3",
        json={"name": "Trade Binder XL"},
        headers={"If-Match": _binder_etag(client, 3)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Trade Binder XL"
    assert body["version"] == 2
    assert body["description"] == "Duplicates and playable cards for locals"
    assert response.headers["etag"].startswith('"binder-3-v2')


def test_update_binder_can_clear_description(client: TestClient) -> None:
    response = client.put(
        "/binders/3",
        json={"description": None},
        headers={"If-Match": _binder_etag(client, 3)},
    )
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_update_missing_binder_returns_404(client: TestClient) -> None:
    response = client.put("/binders/999", json={"name": "X"}, headers={"If-Match": "*"})
    assert response.status_code == 404


def test_update_binder_bumps_version_on_every_write(client: TestClient) -> None:
    first = client.put(
        "/binders/3",
        json={"name": "A"},
        headers={"If-Match": _binder_etag(client, 3)},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2
    second = client.put(
        "/binders/3",
        json={"description": "B"},
        headers={"If-Match": first.headers["etag"]},
    )
    assert second.status_code == 200
    assert second.json()["version"] == 3
    assert second.headers["etag"] != first.headers["etag"]


def test_update_binder_with_stale_etag_returns_412(client: TestClient) -> None:
    stale = _binder_etag(client, 3)
    client.put("/binders/3", json={"name": "A"}, headers={"If-Match": stale})
    response = client.put("/binders/3", json={"name": "B"}, headers={"If-Match": stale})
    assert response.status_code == 412
    assert "current ETag is" in response.json()["detail"]


def test_update_binder_requires_if_match(client: TestClient) -> None:
    response = client.put("/binders/3", json={"name": "X"})
    assert response.status_code == 428


def test_update_binder_accepts_wildcard_if_match(client: TestClient) -> None:
    response = client.put("/binders/3", json={"name": "X"}, headers={"If-Match": "*"})
    assert response.status_code == 200


def test_update_binder_rejects_weak_etag(client: TestClient) -> None:
    etag = _binder_etag(client, 3)
    response = client.put(
        "/binders/3", json={"name": "X"}, headers={"If-Match": f"W/{etag}"}
    )
    assert response.status_code == 412


def test_update_binder_rejects_legacy_version_field(client: TestClient) -> None:
    response = client.put(
        "/binders/3",
        json={"version": 1, "name": "X"},
        headers={"If-Match": _binder_etag(client, 3)},
    )
    assert response.status_code == 422


def test_delete_binder_cascades_to_cards(client: TestClient, database: Engine) -> None:
    response = client.delete(
        "/binders/1", headers={"If-Match": _binder_etag(client, 1)}
    )
    assert response.status_code == 204
    assert client.get("/binders/1").status_code == 404
    with database.connect() as conn:
        remaining = conn.execute(
            text("SELECT count(*) FROM cards WHERE binder_id = 1")
        ).scalar_one()
    assert remaining == 0


def test_delete_binder_with_stale_etag_returns_412(client: TestClient) -> None:
    stale = _binder_etag(client, 3)
    client.put("/binders/3", json={"name": "A"}, headers={"If-Match": stale})
    response = client.delete("/binders/3", headers={"If-Match": stale})
    assert response.status_code == 412
    assert client.get("/binders/3").status_code == 200


def test_delete_binder_requires_if_match(client: TestClient) -> None:
    assert client.delete("/binders/3").status_code == 428


def test_delete_missing_binder_returns_404(client: TestClient) -> None:
    response = client.delete("/binders/999", headers={"If-Match": "*"})
    assert response.status_code == 404

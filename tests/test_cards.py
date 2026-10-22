"""Integration tests for the card endpoints."""

from datetime import date

from fastapi.testclient import TestClient


def test_create_card_applies_defaults(client: TestClient) -> None:
    response = client.post(
        "/cards",
        json={
            "binder_id": 1,
            "name": "Gengar",
            "set_name": "Fossil",
            "collector_number": "5/62",
            "rarity": "Holo Rare",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["binder_id"] == 1
    assert body["variant"] == "Standard"
    assert body["acquired_at"] == date.today().isoformat()
    assert body["version"] == 1
    assert body["certificate"] is None


def test_create_card_in_missing_binder_returns_404(client: TestClient) -> None:
    response = client.post(
        "/cards",
        json={
            "binder_id": 999,
            "name": "Gengar",
            "set_name": "Fossil",
            "collector_number": "5/62",
            "rarity": "Holo Rare",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Binder not found"


def test_create_card_validates_field_lengths(client: TestClient) -> None:
    response = client.post(
        "/cards",
        json={
            "binder_id": 1,
            "name": "x" * 101,
            "set_name": "Fossil",
            "collector_number": "5/62",
            "rarity": "Holo Rare",
        },
    )
    assert response.status_code == 422


def test_create_card_rejects_future_acquired_at(client: TestClient) -> None:
    response = client.post(
        "/cards",
        json={
            "binder_id": 1,
            "name": "Gengar",
            "set_name": "Fossil",
            "collector_number": "5/62",
            "rarity": "Holo Rare",
            "acquired_at": "2999-01-01",
        },
    )
    assert response.status_code == 422


def test_list_cards_returns_seed_data(client: TestClient) -> None:
    response = client.get("/cards")
    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 8
    assert cards[0]["name"] == "Charizard"
    assert cards[0]["certificate"]["grading_company"] == "PSA"


def test_list_cards_filter_binder_id(client: TestClient) -> None:
    response = client.get("/cards", params={"binder_id": 2})
    assert [card["name"] for card in response.json()] == [
        "Umbreon VMAX",
        "Giratina V",
        "Gardevoir ex",
    ]


def test_list_cards_name_filter_is_substring_and_ci(client: TestClient) -> None:
    response = client.get("/cards", params={"name": "char"})
    assert [card["name"] for card in response.json()] == ["Charizard"]


def test_list_cards_rarity_filter_is_exact_and_ci(client: TestClient) -> None:
    response = client.get("/cards", params={"rarity": "holo rare"})
    assert len(response.json()) == 3
    response = client.get("/cards", params={"rarity": "holo"})
    assert response.json() == []


def test_list_cards_variant_filter(client: TestClient) -> None:
    response = client.get("/cards", params={"variant": "alt art"})
    assert [card["name"] for card in response.json()] == [
        "Umbreon VMAX",
        "Giratina V",
    ]


def test_list_cards_acquired_date_range(client: TestClient) -> None:
    response = client.get(
        "/cards", params={"acquired_from": "2024-01-01", "acquired_to": "2024-12-31"}
    )
    assert [card["name"] for card in response.json()] == [
        "Giratina V",
        "Gardevoir ex",
        "Iono",
        "Pidgeot ex",
    ]


def test_list_cards_order_by_acquired_at_desc(client: TestClient) -> None:
    response = client.get("/cards", params={"order_by": "acquired_at", "order": "desc"})
    cards = response.json()
    assert cards[0]["name"] == "Pidgeot ex"
    assert cards[-1]["name"] == "Blastoise"


def test_list_cards_pagination(client: TestClient) -> None:
    response = client.get("/cards", params={"limit": 3, "offset": 8})
    assert response.json() == []


def test_get_card_detail_embeds_certificate(client: TestClient) -> None:
    graded = client.get("/cards/1").json()
    assert graded["certificate"]["cert_number"] == "PSA-84920194"
    raw = client.get("/cards/3").json()
    assert raw["certificate"] is None


def test_get_missing_card_returns_404(client: TestClient) -> None:
    assert client.get("/cards/999").status_code == 404


def _card_etag(client: TestClient, card_id: int) -> str:
    return client.get(f"/cards/{card_id}").headers["etag"]


def test_update_card_is_partial(client: TestClient) -> None:
    response = client.put(
        "/cards/3",
        json={"name": "Blastoise (Base)"},
        headers={"If-Match": _card_etag(client, 3)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Blastoise (Base)"
    assert body["version"] == 2
    assert body["variant"] == "Unlimited"
    assert body["set_name"] == "Base Set"
    assert response.headers["etag"] == '"card-3-v2"'


def test_update_card_can_move_binder(client: TestClient) -> None:
    response = client.put(
        "/cards/3",
        json={"binder_id": 2},
        headers={"If-Match": _card_etag(client, 3)},
    )
    assert response.status_code == 200
    assert response.json()["binder_id"] == 2
    binder_cards = client.get("/binders/2").json()["cards"]
    assert "Blastoise" in [card["name"] for card in binder_cards]


def test_update_card_to_missing_binder_returns_404(client: TestClient) -> None:
    response = client.put(
        "/cards/3",
        json={"binder_id": 999},
        headers={"If-Match": _card_etag(client, 3)},
    )
    assert response.status_code == 404


def test_update_missing_card_returns_404(client: TestClient) -> None:
    response = client.put("/cards/999", json={"name": "X"}, headers={"If-Match": "*"})
    assert response.status_code == 404


def test_update_card_bumps_version_on_every_write(client: TestClient) -> None:
    first = client.put(
        "/cards/3",
        json={"name": "Blastoise (Base)"},
        headers={"If-Match": _card_etag(client, 3)},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2
    second = client.put(
        "/cards/3",
        json={"variant": "Shadowless"},
        headers={"If-Match": first.headers["etag"]},
    )
    assert second.status_code == 200
    assert second.json()["version"] == 3
    assert second.headers["etag"] != first.headers["etag"]


def test_update_card_with_stale_etag_returns_412(client: TestClient) -> None:
    stale = _card_etag(client, 3)
    client.put("/cards/3", json={"name": "A"}, headers={"If-Match": stale})
    response = client.put("/cards/3", json={"name": "B"}, headers={"If-Match": stale})
    assert response.status_code == 412
    assert "current ETag is" in response.json()["detail"]


def test_update_card_requires_if_match(client: TestClient) -> None:
    response = client.put("/cards/3", json={"name": "X"})
    assert response.status_code == 428


def test_update_card_accepts_wildcard_if_match(client: TestClient) -> None:
    response = client.put("/cards/3", json={"name": "X"}, headers={"If-Match": "*"})
    assert response.status_code == 200


def test_update_card_rejects_weak_etag(client: TestClient) -> None:
    etag = _card_etag(client, 3)
    response = client.put(
        "/cards/3", json={"name": "X"}, headers={"If-Match": f"W/{etag}"}
    )
    assert response.status_code == 412


def test_update_card_rejects_legacy_version_field(client: TestClient) -> None:
    response = client.put(
        "/cards/3",
        json={"version": 1, "name": "X"},
        headers={"If-Match": _card_etag(client, 3)},
    )
    assert response.status_code == 422


def test_delete_card(client: TestClient) -> None:
    response = client.delete("/cards/3", headers={"If-Match": _card_etag(client, 3)})
    assert response.status_code == 204
    assert client.get("/cards/3").status_code == 404


def test_delete_card_with_stale_etag_returns_412(client: TestClient) -> None:
    stale = _card_etag(client, 3)
    client.put("/cards/3", json={"name": "A"}, headers={"If-Match": stale})
    response = client.delete("/cards/3", headers={"If-Match": stale})
    assert response.status_code == 412
    assert client.get("/cards/3").status_code == 200


def test_delete_card_requires_if_match(client: TestClient) -> None:
    assert client.delete("/cards/3").status_code == 428


def test_delete_missing_card_returns_404(client: TestClient) -> None:
    response = client.delete("/cards/999", headers={"If-Match": "*"})
    assert response.status_code == 404

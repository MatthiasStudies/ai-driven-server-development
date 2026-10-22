"""Integration tests for the grading certificate endpoints."""

from fastapi.testclient import TestClient

CERT_BODY = {
    "card_id": 3,
    "grading_company": "PSA",
    "cert_number": "PSA-99999999",
    "grade": 9.5,
    "graded_at": "2024-08-01",
}


def test_add_certificate_to_raw_card(client: TestClient) -> None:
    response = client.post("/certificates", json=CERT_BODY)
    assert response.status_code == 201
    body = response.json()
    assert body["card_id"] == 3
    assert body["grade"] == 9.5
    assert body["cert_number"] == "PSA-99999999"
    embedded = client.get("/cards/3").json()["certificate"]
    assert embedded["id"] == body["id"]


def test_add_certificate_to_graded_card_conflicts(client: TestClient) -> None:
    response = client.post("/certificates", json={**CERT_BODY, "card_id": 1})
    assert response.status_code == 409
    assert response.json()["detail"] == "Card is already graded"


def test_duplicate_cert_number_conflicts(client: TestClient) -> None:
    response = client.post(
        "/certificates", json={**CERT_BODY, "cert_number": "PSA-84920194"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Certificate number already exists"


def test_certificate_for_missing_card_returns_404(client: TestClient) -> None:
    response = client.post("/certificates", json={**CERT_BODY, "card_id": 999})
    assert response.status_code == 404
    assert response.json()["detail"] == "Card not found"


def test_certificate_validates_grade_bounds(client: TestClient) -> None:
    assert (
        client.post("/certificates", json={**CERT_BODY, "grade": 10.5}).status_code
        == 422
    )
    assert (
        client.post("/certificates", json={**CERT_BODY, "grade": 0.5}).status_code
        == 422
    )


def test_certificate_validates_graded_at(client: TestClient) -> None:
    response = client.post(
        "/certificates", json={**CERT_BODY, "graded_at": "2999-01-01"}
    )
    assert response.status_code == 422


def test_certificate_validates_field_lengths(client: TestClient) -> None:
    response = client.post(
        "/certificates", json={**CERT_BODY, "grading_company": "x" * 21}
    )
    assert response.status_code == 422


def test_list_certificates_returns_seed_data(client: TestClient) -> None:
    response = client.get("/certificates")
    assert response.status_code == 200
    assert len(response.json()) == 4


def test_list_certificates_filter_company_is_exact_and_ci(client: TestClient) -> None:
    response = client.get("/certificates", params={"grading_company": "psa"})
    assert len(response.json()) == 2
    response = client.get("/certificates", params={"grading_company": "PS"})
    assert response.json() == []


def test_list_certificates_filter_grade_range(client: TestClient) -> None:
    response = client.get("/certificates", params={"grade_min": 9.5})
    grades = [certificate["grade"] for certificate in response.json()]
    assert sorted(grades) == [9.5, 9.5, 10.0]


def test_list_certificates_filter_card_id(client: TestClient) -> None:
    response = client.get("/certificates", params={"card_id": 1})
    assert response.json()[0]["cert_number"] == "PSA-84920194"


def test_list_certificates_order_by_grade_desc(client: TestClient) -> None:
    response = client.get(
        "/certificates", params={"order_by": "grade", "order": "desc"}
    )
    assert response.json()[0]["grade"] == 10.0


def test_get_certificate_detail(client: TestClient) -> None:
    response = client.get("/certificates/2")
    assert response.status_code == 200
    assert response.json()["grading_company"] == "BGS"


def test_get_missing_certificate_returns_404(client: TestClient) -> None:
    assert client.get("/certificates/999").status_code == 404


def test_delete_certificate_allows_regrading(client: TestClient) -> None:
    assert client.delete("/certificates/1").status_code == 204
    assert client.get("/certificates/1").status_code == 404
    response = client.post(
        "/certificates",
        json={
            "card_id": 1,
            "grading_company": "CGC",
            "cert_number": "CGC-11111111",
            "grade": 9.0,
            "graded_at": "2025-01-01",
        },
    )
    assert response.status_code == 201


def test_delete_missing_certificate_returns_404(client: TestClient) -> None:
    assert client.delete("/certificates/999").status_code == 404


def test_card_delete_cascades_certificate(client: TestClient) -> None:
    assert client.delete("/cards/1").status_code == 204
    assert client.get("/certificates/1").status_code == 404

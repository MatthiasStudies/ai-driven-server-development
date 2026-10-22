"""Contract tests for the built-in OpenAPI documentation."""

from fastapi.testclient import TestClient

OPERATION_METHODS = ("get", "post", "put", "delete")


def test_docs_endpoints_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_every_operation_is_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "tcg-card-stack"
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method not in OPERATION_METHODS:
                continue
            assert operation.get("summary"), f"{method.upper()} {path} lacks a summary"
            assert operation.get("tags"), f"{method.upper()} {path} lacks tags"


def test_all_tags_are_declared(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    declared = {tag["name"] for tag in spec["tags"]}
    assert declared == {"meta", "binders", "cards", "certificates", "search"}

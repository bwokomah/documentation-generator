import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app, get_conn


@pytest.fixture
def client():
    conn = get_connection(":memory:")
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, path, name, content_type):
    with open(path, "rb") as f:
        return client.post("/api/documents", files={"file": (name, f.read(), content_type)})


def test_upload_markdown_then_list_and_view(client):
    res = upload(client, "samples/getting-started.md", "getting-started.md", "text/markdown")
    assert res.status_code == 201
    assert res.json()["slug"] == "getting-started"

    assert len(client.get("/api/documents").json()) == 1

    doc = client.get("/api/documents/getting-started").json()
    assert [s["heading"] for s in doc["sections"]] == ["Getting Started", "Installation", "Usage"]


def test_upload_openapi(client):
    res = upload(client, "samples/petstore.yaml", "petstore.yaml", "application/yaml")
    assert res.status_code == 201
    doc = client.get("/api/documents/pet-store-api").json()
    assert len(doc["endpoints"]) == 3


def test_unsupported_file_type_is_rejected(client):
    res = client.post("/api/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 400


def test_empty_markdown_is_rejected(client):
    res = client.post("/api/documents", files={"file": ("empty.md", b"", "text/markdown")})
    assert res.status_code == 422


def test_invalid_openapi_is_rejected(client):
    res = client.post("/api/documents", files={"file": ("bad.yaml", b"hello: world", "application/yaml")})
    assert res.status_code == 422


def test_unknown_document_returns_404(client):
    assert client.get("/api/documents/nope").status_code == 404
    assert client.delete("/api/documents/nope").status_code == 404


def test_delete_document(client):
    upload(client, "samples/getting-started.md", "getting-started.md", "text/markdown")
    assert client.delete("/api/documents/getting-started").status_code == 204
    assert client.get("/api/documents/getting-started").status_code == 404
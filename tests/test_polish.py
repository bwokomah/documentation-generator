import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app, get_conn
from app.seed import seed


@pytest.fixture
def conn():
    return get_connection(":memory:")


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_seed_loads_samples_only_once(conn):
    assert seed(conn) >= 2
    assert seed(conn) == 0


def test_delete_button_route_removes_document(client, conn):
    seed(conn)
    res = client.post("/delete/getting-started", follow_redirects=False)
    assert res.status_code == 303
    assert client.get("/view/getting-started").status_code == 404


def test_oversized_upload_is_rejected(client):
    res = client.post("/api/documents", files={"file": ("big.md", b"a" * 1_000_001, "text/markdown")})
    assert res.status_code == 413


def test_non_utf8_upload_is_rejected(client):
    res = client.post("/api/documents", files={"file": ("bad.md", b"\xff\xfe\x00", "text/markdown")})
    assert res.status_code == 400


def test_markdown_without_headings_still_works(client):
    res = client.post("/api/documents", files={"file": ("notes.md", b"just some text", "text/markdown")})
    assert res.status_code == 201
    assert res.json()["slug"] == "notes"
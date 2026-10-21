import pytest
from fastapi.testclient import TestClient

from app.db import (
    delete_document,
    get_connection,
    rebuild_search_index,
    save_document,
    search_documents,
)
from app.main import app, get_conn
from app.parser.markdown import parse_markdown
from app.parser.openapi import parse_openapi


def markdown_sample():
    with open("samples/getting-started.md") as f:
        return parse_markdown(f.read(), "getting-started.md")


def openapi_sample():
    with open("samples/petstore.yaml") as f:
        return parse_openapi(f.read(), "petstore.yaml")


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    save_document(c, markdown_sample())
    save_document(c, openapi_sample())
    return c


@pytest.fixture
def client(conn):
    app.dependency_overrides[get_conn] = lambda: conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_finds_markdown_section(conn):
    results = search_documents(conn, "installation")
    assert "s2" in [r.anchor for r in results if r.slug == "getting-started"]


def test_finds_api_endpoint_by_response_text(conn):
    results = search_documents(conn, "pet not found")
    assert any(r.slug == "pet-store-api" and r.anchor == "e3" for r in results)


def test_matches_beginning_of_a_word(conn):
    assert search_documents(conn, "inst") != []


def test_no_results_and_odd_queries_do_not_crash(conn):
    assert search_documents(conn, "zzzzzz") == []
    assert search_documents(conn, "") == []
    assert search_documents(conn, '"*(') == []
    assert isinstance(search_documents(conn, 'foo" OR ('), list)


def test_reuploading_does_not_duplicate_results(conn):
    save_document(conn, markdown_sample())
    results = search_documents(conn, "installation")
    assert len([r for r in results if r.anchor == "s2"]) == 1


def test_deleted_document_is_no_longer_searchable(conn):
    delete_document(conn, "getting-started")
    assert search_documents(conn, "installation") == []


def test_rebuild_restores_the_index(conn):
    conn.execute("DELETE FROM search_index")
    assert search_documents(conn, "installation") == []
    rebuild_search_index(conn)
    assert search_documents(conn, "installation") != []


def test_search_api(client):
    res = client.get("/api/search", params={"q": "installation"})
    assert res.status_code == 200
    data = res.json()
    assert data and data[0]["slug"] == "getting-started"


def test_search_page_links_to_the_match_and_shows_empty_state(client):
    res = client.get("/search", params={"q": "installation"})
    assert res.status_code == 200
    assert "/view/getting-started#s2" in res.text
    assert "No results" in client.get("/search", params={"q": "zzzzzz"}).text


def test_search_results_escape_html_from_documents(client):
    client.post(
        "/api/documents",
        files={"file": ("x.md", b"# Hi\n\n<script>alert(1)</script> findme\n", "text/markdown")},
    )
    res = client.get("/search", params={"q": "findme"})
    assert "findme" in res.text
    assert "<script>" not in res.text
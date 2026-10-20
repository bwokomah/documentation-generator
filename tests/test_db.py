from app.db import (
    delete_document,
    get_connection,
    get_document_by_slug,
    list_documents,
    save_document,
)
from app.parser.markdown import parse_markdown
from app.parser.openapi import parse_openapi


def load_markdown_sample():
    with open("samples/getting-started.md") as f:
        return parse_markdown(f.read(), "getting-started.md")


def load_openapi_sample():
    with open("samples/petstore.yaml") as f:
        return parse_openapi(f.read(), "petstore.yaml")


def test_markdown_document_round_trip():
    conn = get_connection(":memory:")
    save_document(conn, load_markdown_sample())

    loaded = get_document_by_slug(conn, "getting-started")
    assert loaded.title == "Getting Started"
    assert [s.heading for s in loaded.sections] == ["Getting Started", "Installation", "Usage"]


def test_openapi_document_round_trip():
    conn = get_connection(":memory:")
    save_document(conn, load_openapi_sample())

    loaded = get_document_by_slug(conn, "pet-store-api")
    assert len(loaded.endpoints) == 3
    assert loaded.endpoints[0].method == "GET"
    assert loaded.endpoints[0].parameters[0]["name"] == "limit"
    assert "404" in loaded.endpoints[2].responses


def test_saving_same_slug_replaces_instead_of_duplicating():
    conn = get_connection(":memory:")
    save_document(conn, load_markdown_sample())
    save_document(conn, load_markdown_sample())
    assert len(list_documents(conn)) == 1


def test_missing_document_returns_none():
    conn = get_connection(":memory:")
    assert get_document_by_slug(conn, "does-not-exist") is None


def test_delete_document():
    conn = get_connection(":memory:")
    save_document(conn, load_markdown_sample())
    assert delete_document(conn, "getting-started") is True
    assert delete_document(conn, "getting-started") is False
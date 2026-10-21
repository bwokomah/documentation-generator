import os
import html
import json
import re
import sqlite3

from app.models import Document, Endpoint, SearchResult, Section

DB_PATH = os.environ.get("DATABASE_PATH", "docgen.db")

# Control characters that mark matches inside snippets. They are swapped for
# <mark> tags only after the text has been HTML-escaped.
MARK_START = "\x02"
MARK_END = "\x03"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    heading TEXT NOT NULL,
    level INTEGER NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    parameters TEXT NOT NULL DEFAULT '[]',   -- stored as JSON
    responses TEXT NOT NULL DEFAULT '{}'     -- stored as JSON
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    slug UNINDEXED,
    doc_title UNINDEXED,
    anchor UNINDEXED,
    heading,
    body,
    tokenize = 'porter unicode61'
);
"""


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    """Open the database (creating it if needed) and make sure the tables exist."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    # Documents saved before search existed get indexed automatically
    index_empty = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0] == 0
    has_documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] > 0
    if index_empty and has_documents:
        rebuild_search_index(conn)

    return conn


def _index_document(conn: sqlite3.Connection, doc: Document) -> None:
    """Add a document's sections and endpoints to the search index."""
    insert = (
        "INSERT INTO search_index (slug, doc_title, anchor, heading, body) "
        "VALUES (?, ?, ?, ?, ?)"
    )

    # Anchors match the ids used in document.html: s1, s2... and e1, e2...
    for pos, s in enumerate(doc.sections):
        conn.execute(insert, (doc.slug, doc.title, f"s{pos + 1}", s.heading, s.body))

    for pos, e in enumerate(doc.endpoints):
        heading = f"{e.method} {e.path} {e.summary}".strip()
        parts = [e.description]
        parts += [f"{p.get('name', '')} {p.get('description', '')}".strip() for p in e.parameters]
        parts += [f"{code} {text}".strip() for code, text in e.responses.items()]
        body = "\n".join(p for p in parts if p)
        conn.execute(insert, (doc.slug, doc.title, f"e{pos + 1}", heading, body))


def rebuild_search_index(conn: sqlite3.Connection) -> None:
    """Throw away the search index and rebuild it from the stored documents."""
    with conn:
        conn.execute("DELETE FROM search_index")
        slugs = [r["slug"] for r in conn.execute("SELECT slug FROM documents").fetchall()]
        for slug in slugs:
            _index_document(conn, get_document_by_slug(conn, slug))


def save_document(conn: sqlite3.Connection, doc: Document) -> int:
    """Store a document. If one with the same slug exists, it is replaced."""
    with conn:  # commits on success, rolls back if anything fails
        conn.execute("DELETE FROM search_index WHERE slug = ?", (doc.slug,))
        conn.execute("DELETE FROM documents WHERE slug = ?", (doc.slug,))
        cur = conn.execute(
            "INSERT INTO documents (title, source_type, slug) VALUES (?, ?, ?)",
            (doc.title, doc.source_type, doc.slug),
        )
        doc_id = cur.lastrowid

        for pos, s in enumerate(doc.sections):
            conn.execute(
                "INSERT INTO sections (document_id, position, heading, level, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (doc_id, pos, s.heading, s.level, s.body),
            )

        for pos, e in enumerate(doc.endpoints):
            conn.execute(
                "INSERT INTO endpoints (document_id, position, method, path, summary, "
                "description, parameters, responses) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, pos, e.method, e.path, e.summary, e.description,
                 json.dumps(e.parameters), json.dumps(e.responses)),
            )

        _index_document(conn, doc)

    doc.id = doc_id
    return doc_id


def get_document_by_slug(conn: sqlite3.Connection, slug: str) -> Document | None:
    row = conn.execute("SELECT * FROM documents WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None

    sections = [
        Section(heading=r["heading"], level=r["level"], body=r["body"])
        for r in conn.execute(
            "SELECT * FROM sections WHERE document_id = ? ORDER BY position", (row["id"],)
        )
    ]
    endpoints = [
        Endpoint(
            method=r["method"],
            path=r["path"],
            summary=r["summary"],
            description=r["description"],
            parameters=json.loads(r["parameters"]),
            responses=json.loads(r["responses"]),
        )
        for r in conn.execute(
            "SELECT * FROM endpoints WHERE document_id = ? ORDER BY position", (row["id"],)
        )
    ]
    return Document(
        id=row["id"],
        title=row["title"],
        source_type=row["source_type"],
        slug=row["slug"],
        sections=sections,
        endpoints=endpoints,
    )


def list_documents(conn: sqlite3.Connection) -> list[Document]:
    """Return every document with just id, title, slug and type (used by the sidebar)."""
    rows = conn.execute("SELECT * FROM documents ORDER BY title").fetchall()
    return [
        Document(id=r["id"], title=r["title"], source_type=r["source_type"], slug=r["slug"])
        for r in rows
    ]


def delete_document(conn: sqlite3.Connection, slug: str) -> bool:
    with conn:
        conn.execute("DELETE FROM search_index WHERE slug = ?", (slug,))
        cur = conn.execute("DELETE FROM documents WHERE slug = ?", (slug,))
    return cur.rowcount > 0


def search_documents(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[SearchResult]:
    """Full-text search across all documents, best matches first."""
    # Keep only plain words, so characters with special meaning in FTS5 syntax
    # (quotes, parentheses, AND/OR...) can never break the query.
    words = re.findall(r"\w+", query or "")
    if not words:
        return []
    fts_query = " ".join(f'"{w}"*' for w in words)  # every word must match; "*" = prefix

    rows = conn.execute(
        "SELECT slug, doc_title, anchor, heading, "
        "       snippet(search_index, -1, ?, ?, '…', 20) AS snip "
        "FROM search_index WHERE search_index MATCH ? "
        "ORDER BY bm25(search_index, 0, 0, 0, 5.0, 1.0) "  # heading matches count 5x
        "LIMIT ?",
        (MARK_START, MARK_END, fts_query, limit),
    ).fetchall()

    return [
        SearchResult(
            slug=r["slug"],
            doc_title=r["doc_title"],
            anchor=r["anchor"],
            heading=r["heading"],
            snippet=html.escape(r["snip"]).replace(MARK_START, "<mark>").replace(MARK_END, "</mark>"),
        )
        for r in rows
    ]
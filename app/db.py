import json
import sqlite3

from app.models import Document, Endpoint, Section

DB_PATH = "docgen.db"

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
"""


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    """Open the database (creating it if needed) and make sure the tables exist."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def save_document(conn: sqlite3.Connection, doc: Document) -> int:
    """Store a document. If one with the same slug exists, it is replaced."""
    with conn:  # commits on success, rolls back if anything fails
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
        cur = conn.execute("DELETE FROM documents WHERE slug = ?", (slug,))
    return cur.rowcount > 0
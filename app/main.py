from dataclasses import asdict

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

from app.db import (
    delete_document,
    get_connection,
    get_document_by_slug,
    list_documents,
    save_document,
)
from app.parser.markdown import parse_markdown
from app.parser.openapi import parse_openapi

MAX_UPLOAD_BYTES = 1_000_000  # 1 MB

MARKDOWN_EXTENSIONS = (".md", ".markdown")
OPENAPI_EXTENSIONS = (".yaml", ".yml", ".json")

app = FastAPI(title="Documentation Generator")

_conn = None


def get_conn():
    """One shared database connection for the whole app (tests replace this)."""
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), conn=Depends(get_conn)):
    filename = (file.filename or "").lower()

    if filename.endswith(MARKDOWN_EXTENSIONS):
        parse = parse_markdown
    elif filename.endswith(OPENAPI_EXTENSIONS):
        parse = parse_openapi
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload .md, .yaml, .yml or .json",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (limit is 1 MB)")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")

    try:
        doc = parse(text, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    save_document(conn, doc)
    return {"id": doc.id, "title": doc.title, "slug": doc.slug, "source_type": doc.source_type}


@app.get("/api/documents")
def get_documents(conn=Depends(get_conn)):
    return [
        {"id": d.id, "title": d.title, "slug": d.slug, "source_type": d.source_type}
        for d in list_documents(conn)
    ]


@app.get("/api/documents/{slug}")
def get_document(slug: str, conn=Depends(get_conn)):
    doc = get_document_by_slug(conn, slug)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return asdict(doc)


@app.delete("/api/documents/{slug}", status_code=204)
def remove_document(slug: str, conn=Depends(get_conn)):
    if not delete_document(conn, slug):
        raise HTTPException(status_code=404, detail="Document not found")
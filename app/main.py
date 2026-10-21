from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import (
    delete_document,
    get_connection,
    get_document_by_slug,
    list_documents,
    save_document,
)
from app.models import Document
from app.parser.markdown import parse_markdown
from app.parser.openapi import parse_openapi
from app.renderer import templates

MAX_UPLOAD_BYTES = 1_000_000  # 1 MB

MARKDOWN_EXTENSIONS = (".md", ".markdown")
OPENAPI_EXTENSIONS = (".yaml", ".yml", ".json")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Documentation Generator")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

_conn = None


def get_conn():
    """One shared database connection for the whole app (tests replace this)."""
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn


async def parse_upload(file: UploadFile) -> Document:
    """Validate an uploaded file and turn it into a Document."""
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
        return parse(text, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def page(request: Request, name: str, conn, status_code: int = 200, **context):
    """Render an HTML page; every page gets the document list for the sidebar."""
    context["documents"] = list_documents(conn)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


# ---------- JSON API ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), conn=Depends(get_conn)):
    doc = await parse_upload(file)
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


# ---------- HTML pages ----------

@app.get("/")
def home(request: Request, conn=Depends(get_conn)):
    return page(request, "index.html", conn)


@app.post("/upload")
async def upload_form(request: Request, file: UploadFile = File(...), conn=Depends(get_conn)):
    try:
        doc = await parse_upload(file)
    except HTTPException as e:
        return page(request, "index.html", conn, status_code=e.status_code, error=e.detail)
    save_document(conn, doc)
    return RedirectResponse(f"/view/{doc.slug}", status_code=303)


@app.get("/view/{slug}")
def view_document(request: Request, slug: str, conn=Depends(get_conn)):
    doc = get_document_by_slug(conn, slug)
    if doc is None:
        return page(request, "index.html", conn, status_code=404, error="Document not found")
    return page(request, "document.html", conn, doc=doc, current=slug)
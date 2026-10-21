# Documentation Generator

Upload Markdown files or OpenAPI specs and get a searchable documentation website.

**Live demo:** [YOUR-LIVE-URL](http://127.0.0.1:8000/)
**Team:** Bright (lead), Amanda

## Features
- Upload `.md`, `.yaml`, `.yml` or `.json` files through a web form or the API
- Markdown pages with a table of contents; OpenAPI specs rendered as endpoint cards with parameter and response tables
- Full-text search across all documents (ranked, prefix matching, highlighted snippets)
- Sidebar navigation, delete button, sample data loaded automatically
- Clear errors for bad input (empty file, invalid OpenAPI, wrong type, too large, not UTF-8)

## Tech stack
Python, FastAPI, Jinja2, markdown-it-py, PyYAML, openapi-spec-validator, SQLite (FTS5 for search), pytest.

## Setup
```bash
git clone https://github.com/bwokomah/documentation-generator.git
cd documentation-generator
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/ (web app) or http://127.0.0.1:8000/docs (interactive API explorer).

## Environment variables
| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_PATH` | `docgen.db` | Where the SQLite file is stored |
| `SEED_SAMPLES` | `1` | Load the files in `samples/` on startup if the database is empty. Set to `0` to disable |
| `PORT` | set by the host | Port the server listens on in production (passed to uvicorn in the start command) |

## Tests
```bash
python -m pytest -v
```
Covers the parsers' happy and failure paths, the database round trip, every API route, the HTML pages, search, and security checks (HTML inside uploads is escaped).

## API
| Method | Path | Description |
|---|---|---|
| POST | `/api/documents` | Upload a file (multipart field `file`). 201 on success; 400, 413 or 422 on bad input |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{slug}` | One document with all sections or endpoints |
| DELETE | `/api/documents/{slug}` | Delete a document (204) |
| GET | `/api/search?q=...` | Search; returns matches with an anchor into the page |
| GET | `/health` | Health check |

Web pages: `/` (upload), `/view/{slug}` (document), `/search?q=...` (results).

## Data model
Python dataclasses in `app/models.py`: `Document` (title, source_type, slug, sections, endpoints), `Section` (heading, level, body), `Endpoint` (method, path, summary, description, parameters, responses), `SearchResult`.

SQLite schema (`app/db.py`):

| Table | Columns |
|---|---|
| `documents` | id, title, source_type (`markdown` or `openapi`), slug (unique), created_at |
| `sections` | id, document_id, position, heading, level, body (original Markdown) |
| `endpoints` | id, document_id, position, method, path, summary, description, parameters (JSON), responses (JSON) |
| `search_index` | FTS5 virtual table: slug, doc_title, anchor, heading, body |

Deleting a document cascades to its sections and endpoints, and its search entries are removed in the same transaction.

## How it works
1. **Parser** (`app/parser/`) turns an uploaded file into a `Document`, or raises a `ValueError` with a readable message.
2. **Database** (`app/db.py`) stores it and indexes its text for search in one all-or-nothing transaction.
3. **Renderer** (`app/renderer.py` and `app/templates/`) turns a stored `Document` into HTML.
4. **Routes** (`app/main.py`) connect upload, view, search and delete.

## Design decisions and trade-offs
- **SQLite with FTS5** instead of a separate search service: no extra infrastructure and easy to deploy, but one process and one file only.
- **Server-rendered HTML** instead of a JavaScript frontend: fewer moving parts and faster to build, with less interactivity.
- **Raw HTML in uploaded Markdown is shown as text**, so an uploaded file cannot inject scripts into pages.
- **Search input is reduced to plain words** before reaching FTS5, so odd characters cannot break queries.
- **Re-uploading a file replaces the existing document** (same slug) instead of creating duplicates.

## Known limitations
- No login: anyone with the URL can upload or delete documents.
- Large Markdown files are one page; there is no pagination.
- OpenAPI parameters defined through `$ref` are skipped, and only OpenAPI 3.x specs were tested.
- On a free host the filesystem is temporary, so uploads disappear on restart (sample data is re-seeded).

## Next improvements
Authentication and per-user documents, `$ref` resolution for OpenAPI, a persistent database (Postgres), versioned documents, and usage metrics.
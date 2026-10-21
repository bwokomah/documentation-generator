# Demo script (about 6 minutes)

## 1. The problem (30 s)
Teams keep docs as Markdown files and API specs as YAML, and nobody wants to read raw files.
We built a tool that turns both into one searchable documentation site.

## 2. Live flow (2.5 min)
1. Open the live URL. The sidebar already shows the sample docs.
2. Click **Getting Started**: headings, table of contents, a code block.
3. Click **Pet Store API**: method badges, parameter and response tables.
4. Click **+ Upload a file**, upload a new .md file, and land on its rendered page.
5. Search for a word from that file; it appears in the results highlighted.
   Search "pet not found" to show it finds text inside API responses.
6. Failure path: upload an empty file or a broken YAML file and show the clear error message.

## 3. Architecture (1.5 min)
Upload, then parser, then SQLite plus search index, then renderer, then browser.
- Parser: two modules (Markdown, OpenAPI), both produce the same `Document` model.
- Database: three tables plus an FTS5 search table, written in one transaction.
- Renderer: Jinja2 templates; Markdown rendered with raw HTML turned off.
- API: the same logic is exposed as JSON endpoints (show `/docs`).

## 4. Decisions and trade-offs (1 min)
- SQLite FTS5 instead of Elasticsearch: simpler and free to host, but single-node.
- Server-rendered pages instead of a React app: faster for a two-person team.
- Security: uploaded HTML is escaped; search queries are sanitised.
- Free hosting means uploads reset on restart; sample data is re-seeded.

## 5. Done and next (30 s)
Done: parsing, rendering, search, validation, 32 automated tests, deployment.
Next: login, `$ref` support in OpenAPI, a persistent database, usage metrics.
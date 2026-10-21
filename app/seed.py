from pathlib import Path

from app.db import list_documents, save_document
from app.parser.markdown import parse_markdown
from app.parser.openapi import parse_openapi

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def seed(conn, samples_dir: Path = SAMPLES_DIR) -> int:
    """Load the sample files, but only if the database is empty. Returns how many were loaded."""
    if list_documents(conn):
        return 0

    count = 0
    for path in sorted(Path(samples_dir).iterdir()):
        suffix = path.suffix.lower()
        if suffix in (".md", ".markdown"):
            parse = parse_markdown
        elif suffix in (".yaml", ".yml", ".json"):
            parse = parse_openapi
        else:
            continue
        save_document(conn, parse(path.read_text(encoding="utf-8"), path.name))
        count += 1
    return count
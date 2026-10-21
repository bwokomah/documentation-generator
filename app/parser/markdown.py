import re
from pathlib import Path

from markdown_it import MarkdownIt

from app.models import Document, Section


def make_slug(text: str) -> str:
    """Turn 'Getting Started!' into 'getting-started'."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def parse_markdown(text: str, filename: str = "untitled.md") -> Document:
    if not text or not text.strip():
        raise ValueError("Markdown file is empty")

    lines = text.splitlines()
    tokens = MarkdownIt().parse(text)

    # Find every heading and the line numbers it occupies
    headings = []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            headings.append({
                "heading": tokens[i + 1].content,
                "level": int(tok.tag[1]),
                "start": tok.map[0],
                "end": tok.map[1],
            })

    sections: list[Section] = []

    # Text before the first heading becomes an "Introduction" section
    first_start = headings[0]["start"] if headings else len(lines)
    intro = "\n".join(lines[:first_start]).strip()
    if intro:
        sections.append(Section(heading="Introduction", level=2, body=intro))

    # Each section's body is the original Markdown up to the next heading
    for n, h in enumerate(headings):
        next_start = headings[n + 1]["start"] if n + 1 < len(headings) else len(lines)
        body = "\n".join(lines[h["end"]:next_start]).strip()
        sections.append(Section(heading=h["heading"], level=h["level"], body=body))

    # Title = first level-1 heading, otherwise the file name
    title = next((h["heading"] for h in headings if h["level"] == 1), Path(filename).stem)

    return Document(
        title=title,
        source_type="markdown",
        slug=make_slug(title),
        sections=sections,
    )
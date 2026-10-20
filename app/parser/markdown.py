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

    tokens = MarkdownIt().parse(text)
    sections: list[Section] = []
    current = None
    i = 0

    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            # tokens[i] = heading_open, [i+1] = the heading text, [i+2] = heading_close
            current = Section(heading=tokens[i + 1].content, level=int(tok.tag[1]), body="")
            sections.append(current)
            i += 3
            continue

        if tok.type in ("inline", "fence", "code_block"):
            if current is None:
                # text that appears before the first heading
                current = Section(heading="Introduction", level=1, body="")
                sections.append(current)
            current.body += tok.content + "\n"

        i += 1

    for section in sections:
        section.body = section.body.strip()

    # Title = first level-1 heading, otherwise the file name
    title = next((s.heading for s in sections if s.level == 1), Path(filename).stem)

    return Document(
        title=title,
        source_type="markdown",
        slug=make_slug(title),
        sections=sections,
    )
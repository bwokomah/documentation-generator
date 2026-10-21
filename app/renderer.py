from pathlib import Path

from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup

BASE_DIR = Path(__file__).resolve().parent

# html=False means raw HTML typed inside an uploaded file is shown as text, never run
_md = MarkdownIt("commonmark", {"html": False})


def render_markdown(text: str) -> Markup:
    return Markup(_md.render(text or ""))


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["markdown"] = render_markdown
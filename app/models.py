from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    heading: str
    level: int            # 1 for #, 2 for ##, etc.
    body: str             # text content of the section


@dataclass
class Endpoint:
    method: str           # GET, POST, ...
    path: str             # /users/{id}
    summary: str = ""
    description: str = ""
    parameters: list[dict] = field(default_factory=list)
    responses: dict = field(default_factory=dict)   # status code -> description


@dataclass
class Document:
    title: str
    source_type: str                      # "markdown" or "openapi"
    slug: str                             # URL-friendly id, e.g. "getting-started"
    sections: list[Section] = field(default_factory=list)      # used for markdown
    endpoints: list[Endpoint] = field(default_factory=list)    # used for openapi
    id: Optional[int] = None              # set by the database
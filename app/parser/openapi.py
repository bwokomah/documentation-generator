import yaml
from openapi_spec_validator import validate

from app.models import Document, Endpoint
from app.parser.markdown import make_slug

HTTP_METHODS = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]


def parse_openapi(text: str, filename: str = "api") -> Document:
    if not text or not text.strip():
        raise ValueError("OpenAPI file is empty")

    # YAML parsing also handles JSON files, since JSON is valid YAML
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"Could not read file: {e}")

    if not isinstance(spec, dict):
        raise ValueError("File is not a valid OpenAPI document")

    try:
        validate(spec)
    except Exception as e:
        raise ValueError(f"Invalid OpenAPI spec: {e}")

    endpoints: list[Endpoint] = []
    for path, path_item in spec.get("paths", {}).items():
        shared_params = path_item.get("parameters", [])
        for method in HTTP_METHODS:
            op = path_item.get(method)
            if op is None:
                continue
            params = [
                {
                    "name": p.get("name", ""),
                    "in": p.get("in", ""),
                    "required": p.get("required", False),
                    "description": p.get("description", ""),
                }
                for p in shared_params + op.get("parameters", [])
                if "name" in p  # skips unresolved $ref parameters
            ]
            responses = {
                str(code): r.get("description", "")
                for code, r in op.get("responses", {}).items()
            }
            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    summary=op.get("summary", ""),
                    description=op.get("description", ""),
                    parameters=params,
                    responses=responses,
                )
            )

    title = spec.get("info", {}).get("title", filename)
    return Document(
        title=title,
        source_type="openapi",
        slug=make_slug(title),
        endpoints=endpoints,
    )
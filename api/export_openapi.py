"""Write the API's OpenAPI schema to api/openapi.json.

The web app generates its TypeScript types from that file (`npm run gen:api` in web/).
Run from the project root after changing an endpoint or a request or response model:

    python -m api.export_openapi

A test fails when the committed file is out of date.
"""
import json
from pathlib import Path

from api.main import create_app
from api.settings import Settings

OPENAPI_PATH = Path(__file__).resolve().parent / "openapi.json"


def build_schema_text() -> str:
    # Default settings, so the file never depends on the environment it was exported from
    app = create_app(Settings())
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    OPENAPI_PATH.write_text(build_schema_text(), encoding="utf-8", newline="\n")
    print(f"Wrote {OPENAPI_PATH}")


if __name__ == "__main__":
    main()

"""The API contract: the exported OpenAPI file, the documented shapes and the real answers must agree."""
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from api.export_openapi import OPENAPI_PATH, build_schema_text
from api.main import app
from api.schemas import FeatureName, InsightsResponse, MetaResponse
from ml.pipeline import FEATURES

EXPECTED_PATHS = {"/health", "/meta", "/predict", "/what-if", "/predict/batch", "/template.csv", "/insights"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_exported_openapi_file_is_up_to_date():
    committed = OPENAPI_PATH.read_text(encoding="utf-8")
    assert committed == build_schema_text(), (
        "api/openapi.json is out of date. Run `python -m api.export_openapi`, then `npm run gen:api` in web/."
    )


def test_every_endpoint_is_in_the_schema():
    import json
    spec = json.loads(build_schema_text())
    assert set(spec["paths"]) == EXPECTED_PATHS
    for name in ("Student", "PredictResponse", "WhatIfRequest", "BatchResponse", "MetaResponse", "InsightsResponse"):
        assert name in spec["components"]["schemas"], name


def test_feature_names_match_the_model_columns():
    assert list(get_args(FeatureName)) == FEATURES


def test_meta_answer_matches_its_documented_shape(client):
    # extra="forbid" on the model means a field added to /meta without documenting it fails here
    MetaResponse.model_validate(client.get("/meta").json())


def test_insights_answer_matches_its_documented_shape(client):
    InsightsResponse.model_validate(client.get("/insights").json())


def test_error_answers_match_the_documented_shape(client, student):
    from api.schemas import ErrorResponse
    payload = student.iloc[0].to_dict()
    cases = [
        client.post("/predict", json={**payload, "gender": "Robot"}),   # a check of our own: messages
        client.post("/predict", json={**payload, "age": 5}),            # a field check by FastAPI: details
        client.post("/predict", json={**payload, "age": True}),         # a number field given true
        client.post("/predict/batch", files={"file": ("x.csv", b"", "text/csv")}),
    ]
    for res in cases:
        assert res.status_code == 422, res.text
        ErrorResponse.model_validate(res.json())

    # A body that is not valid UTF-8 text is answered with 400 and a single message
    broken = client.post("/predict", content=bytes([0x80, 0x81]), headers={"Content-Type": "application/json"})
    assert broken.status_code == 400
    ErrorResponse.model_validate(broken.json())

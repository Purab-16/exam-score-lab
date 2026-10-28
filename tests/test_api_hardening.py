"""Tests for the API hardening: settings, security headers, gzip, cache headers, size and rate limits.

Each test builds its own app from explicit settings, so they do not depend on the environment.
"""
import time

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import create_app
from api.middleware import RateLimitMiddleware
from api.settings import Settings, parse_rate

ORIGIN = "http://localhost:3000"


@pytest.fixture
def client_for():
    """client_for(**settings) -> a running TestClient. Rate limiting is off unless asked for."""
    opened = []

    def build(**overrides):
        app = create_app(Settings(**{"rate_limit": False, **overrides}))
        client = TestClient(app)
        client.__enter__()
        opened.append(client)
        return client

    yield build
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def payload(student):
    return student.iloc[0].to_dict()


@pytest.fixture
def template_csv(client_for):
    return client_for().get("/template.csv").content


def post_batch(client, content, **kwargs):
    return client.post("/predict/batch", files={"file": ("s.csv", content, "text/csv")}, **kwargs)


# ---------- settings ----------

def test_settings_defaults_are_the_safe_choice():
    s = Settings()
    assert s.api_env == "development" and s.docs_enabled
    assert s.security_headers and s.gzip and s.cache_headers and s.body_limit and s.rate_limit
    assert s.explainer == "auto"
    assert s.max_upload_bytes == 5 * 1024 * 1024


def test_settings_from_env_overrides():
    s = Settings.from_env({
        "API_ENV": "Production", "GZIP_ENABLED": "off", "RATE_LIMIT_BATCH": "2/hour", "MAX_UPLOAD_MB": "1",
        "API_CORS_ORIGINS": "https://a.example, https://b.example", "SECURITY_HEADERS_ENABLED": "0",
    })
    assert s.api_env == "production" and not s.docs_enabled
    assert not s.gzip and not s.security_headers
    assert s.rate_rules()[("POST", "/predict/batch")] == (2, 3600.0)
    assert s.max_upload_bytes == 1024 * 1024
    assert s.cors_origins == ("https://a.example", "https://b.example")
    assert Settings.from_env({"EXPLAINER": "SHAP"}).explainer == "shap"


@pytest.mark.parametrize("env", [
    {"GZIP_ENABLED": "maybe"}, {"API_ENV": "staging"}, {"RATE_LIMIT_PREDICT": "fast"},
    {"RATE_LIMIT_BATCH": "0/minute"}, {"RATE_LIMIT_DEFAULT": "10/day"}, {"EXPLAINER": "magic"},
])
def test_settings_fail_fast_on_bad_values(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_parse_rate():
    assert parse_rate("60/minute") == (60, 60.0)
    assert parse_rate(" 5 / SECOND ") == (5, 1.0)


# ---------- security headers ----------

def test_security_headers_on_every_response(client_for):
    client = client_for()
    for path in ("/health", "/meta", "/does-not-exist"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff", path
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer"
        assert "geolocation=()" in h["permissions-policy"]
        assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_post_responses_are_not_cached(client_for, payload):
    res = client_for().post("/predict", json=payload)
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store"


def test_security_headers_can_be_switched_off(client_for):
    h = client_for(security_headers=False).get("/health").headers
    assert "x-content-type-options" not in h and "content-security-policy" not in h


def test_docs_page_is_not_blocked_by_the_api_csp(client_for):
    res = client_for(api_env="development").get("/docs")
    assert res.status_code == 200
    assert "content-security-policy" not in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"


# ---------- docs ----------

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_available_in_development(client_for, path):
    assert client_for(api_env="development").get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_hidden_in_production(client_for, path):
    client = client_for(api_env="production")
    assert client.get(path).status_code == 404
    assert client.get("/health").status_code == 200


# ---------- gzip ----------

def test_big_responses_are_compressed(client_for):
    res = client_for().get("/insights", headers={"Accept-Encoding": "gzip"})
    assert res.headers["content-encoding"] == "gzip"
    assert int(res.headers["content-length"]) < len(res.content) / 3
    assert res.json()["count"] == 1000  # still decodes to the same data


def test_small_responses_are_left_alone(client_for):
    assert "content-encoding" not in client_for().get("/health", headers={"Accept-Encoding": "gzip"}).headers


def test_gzip_can_be_switched_off(client_for):
    res = client_for(gzip=False).get("/insights", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in res.headers


# ---------- cache headers ----------

@pytest.mark.parametrize("path", ["/meta", "/insights", "/template.csv"])
def test_static_data_has_etag_and_answers_304(client_for, path):
    client = client_for()
    first = client.get(path)
    etag = first.headers["etag"]
    assert first.status_code == 200
    assert first.headers["cache-control"] == "public, max-age=300"

    for sent in (etag, f"W/{etag}", "*", f'"nope", {etag}'):
        again = client.get(path, headers={"If-None-Match": sent})
        assert again.status_code == 304, sent
        assert again.content == b"" and again.headers["etag"] == etag

    assert client.get(path, headers={"If-None-Match": '"stale"'}).status_code == 200


def test_cache_headers_can_be_switched_off(client_for):
    client = client_for(cache_headers=False)
    first = client.get("/meta")
    assert "etag" not in first.headers and "cache-control" not in first.headers
    assert client.get("/meta", headers={"If-None-Match": "*"}).status_code == 200


def test_template_keeps_its_download_name(client_for):
    res = client_for().get("/template.csv")
    assert res.headers["content-disposition"] == 'attachment; filename="students_template.csv"'
    assert res.headers["content-type"].startswith("text/csv")


# ---------- request size limits ----------

def test_oversized_upload_is_rejected_by_the_middleware(client_for, template_csv):
    client = client_for(max_upload_bytes=1024 * 1024)
    big = b"a,b\n" + b"1,2\n" * 320_000  # about 1.3 MB, beyond limit plus multipart framing
    res = post_batch(client, big)
    assert res.status_code == 413
    assert res.json() == {"detail": ["File is larger than 1 MB."]}
    assert post_batch(client, template_csv).status_code == 200  # normal uploads still work


def test_upload_just_over_the_limit_gets_the_same_message(client_for):
    client = client_for(max_upload_bytes=1024 * 1024)
    res = post_batch(client, b"a,b\n" + b"1,2\n" * 270_000)  # about 1.03 MB: passes the middleware
    assert res.status_code == 413
    assert res.json() == {"detail": ["File is larger than 1 MB."]}


def test_json_bodies_have_a_small_limit(client_for, payload):
    import json
    client = client_for(max_json_body_bytes=1024)
    padded = json.dumps(payload) + " " * 3000
    res = client.post("/predict", content=padded, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert res.json() == {"detail": ["Request body is larger than 1 KB."]}
    assert client.post("/predict", json=payload).status_code == 200


def test_streamed_body_without_content_length_is_cut(client_for):
    client = client_for(max_json_body_bytes=4096)

    def chunks():
        for _ in range(40):
            yield b"x" * 1024

    res = client.post("/predict", content=chunks(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_size_limit_can_be_switched_off(client_for, payload):
    import json
    client = client_for(body_limit=False, max_json_body_bytes=1024)
    padded = json.dumps(payload) + " " * 3000
    assert client.post("/predict", content=padded, headers={"Content-Type": "application/json"}).status_code == 200


def test_errors_still_carry_cors_headers(client_for):
    client = client_for(max_upload_bytes=1024 * 1024)
    res = post_batch(client, b"a,b\n" + b"1,2\n" * 320_000, headers={"Origin": ORIGIN})
    assert res.status_code == 413
    assert res.headers["access-control-allow-origin"] == ORIGIN


# ---------- rate limiting ----------

def test_rate_limit_blocks_after_the_limit(client_for, template_csv):
    client = client_for(rate_limit=True, rate_limit_batch="2/minute")
    assert post_batch(client, template_csv).status_code == 200
    assert post_batch(client, template_csv).status_code == 200

    blocked = post_batch(client, template_csv, headers={"Origin": ORIGIN})
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["retry-after"]) <= 60
    assert blocked.json()["detail"][0].startswith("Too many requests")
    assert blocked.headers["access-control-allow-origin"] == ORIGIN
    assert blocked.headers["x-content-type-options"] == "nosniff"


def test_rate_limit_routes_are_counted_separately_and_health_is_exempt(client_for, template_csv, payload):
    client = client_for(rate_limit=True, rate_limit_batch="1/minute", rate_limit_default="3/minute")
    assert post_batch(client, template_csv).status_code == 200
    assert post_batch(client, template_csv).status_code == 429
    assert client.post("/predict", json=payload).status_code == 200  # own bucket

    assert [client.get("/meta").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert all(client.get("/health").status_code == 200 for _ in range(20))


def test_rate_limit_is_per_client(client_for, template_csv):
    client = client_for(rate_limit=True, rate_limit_batch="1/minute")
    other = TestClient(client.app, client=("10.0.0.2", 50000))
    assert post_batch(client, template_csv).status_code == 200
    assert post_batch(client, template_csv).status_code == 429
    assert post_batch(other, template_csv).status_code == 200


def test_rate_limit_can_be_switched_off(client_for, template_csv):
    client = client_for(rate_limit=False, rate_limit_batch="1/minute")
    assert [post_batch(client, template_csv).status_code for _ in range(3)] == [200, 200, 200]


def test_rate_limit_window_slides():
    now = [100.0]
    limiter = RateLimitMiddleware(app=None, rules={None: (5, 60.0)}, clock=lambda: now[0])
    key = ("ip", "bucket")
    assert [limiter._check(key, 2, 10.0) for _ in range(2)] == [0, 0]
    assert limiter._check(key, 2, 10.0) == 10  # full window to wait
    now[0] += 4
    assert limiter._check(key, 2, 10.0) == 6
    now[0] += 7  # first hits have left the window
    assert limiter._check(key, 2, 10.0) == 0


def test_rate_limit_forgets_idle_clients():
    now = [0.0]
    limiter = RateLimitMiddleware(app=None, rules={None: (5, 60.0)}, clock=lambda: now[0])
    for i in range(10):
        limiter._check((f"ip{i}", "b"), 5, 10.0)
    assert len(limiter._hits) == 10
    now[0] = 1000.0
    limiter._prune(now[0])
    assert limiter._hits == {}


# ---------- strict input ----------

def test_unknown_fields_are_rejected(client_for, payload):
    client = client_for()
    assert client.post("/predict", json={**payload, "height": 180}).status_code == 422
    body = {"student": payload, "changes": {}, "note": "x"}
    assert client.post("/what-if", json=body).status_code == 422


def test_over_long_text_is_rejected(client_for, payload):
    assert client_for().post("/predict", json={**payload, "gender": "x" * 41}).status_code == 422


def test_what_if_changes_are_capped(client_for, payload):
    changes = {f"f{i}": 1 for i in range(15)}
    assert client_for().post("/what-if", json={"student": payload, "changes": changes}).status_code == 422


# ---------- batch runs off the event loop ----------

def test_batch_does_not_block_other_requests(monkeypatch, template_csv):
    """While a slow batch is processed, /health must still answer straight away."""
    real_validate = api_main.validate_batch

    def slow_validate(*args, **kwargs):
        time.sleep(0.6)  # stands in for a big upload; blocks whatever thread it runs in
        return real_validate(*args, **kwargs)

    monkeypatch.setattr(api_main, "validate_batch", slow_validate)
    app = create_app(Settings(rate_limit=False))
    seen = {}

    async def scenario():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                async def batch():
                    res = await client.post("/predict/batch", files={"file": ("s.csv", template_csv, "text/csv")})
                    seen["batch_status"], seen["batch_done"] = res.status_code, time.perf_counter()

                async def health():
                    await anyio.sleep(0.15)  # the batch is now busy
                    started = time.perf_counter()
                    res = await client.get("/health")
                    seen["health_status"], seen["health_done"] = res.status_code, time.perf_counter()
                    seen["health_secs"] = seen["health_done"] - started

                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(batch)
                    tasks.start_soon(health)

    anyio.run(scenario)
    assert seen["batch_status"] == 200 and seen["health_status"] == 200
    assert seen["health_secs"] < 0.3
    assert seen["health_done"] < seen["batch_done"]


# ---------- numbers must be numbers ----------

NUMBER_FIELDS = ["age", "study_hours_per_day", "social_media_hours", "netflix_hours", "attendance_percentage",
                 "sleep_hours", "exercise_frequency", "mental_health_rating"]


@pytest.mark.parametrize("field", NUMBER_FIELDS)
@pytest.mark.parametrize("bad", [True, False, "3", "abc"])
def test_number_fields_reject_booleans_and_text(client_for, payload, field, bad):
    assert client_for().post("/predict", json={**payload, field: bad}).status_code == 422


def test_numbers_in_other_forms_still_work(client_for, payload):
    client = client_for()
    assert client.post("/predict", json={**payload, "age": 21.0}).status_code == 200            # whole number as 21.0
    assert client.post("/predict", json={**payload, "study_hours_per_day": 4}).status_code == 200  # integer for a decimal


def test_what_if_numbers_must_be_numbers_too(client_for, payload):
    client = client_for()
    ok = client.post("/what-if", json={"student": payload, "changes": {"exercise_frequency": 4}})
    assert ok.status_code == 200  # a whole number arrives as 4.0 inside the changes
    for bad in (True, "5"):
        res = client.post("/what-if", json={"student": payload, "changes": {"study_hours_per_day": bad}})
        assert res.status_code == 422, bad


def test_limit_errors_match_the_documented_error_shape(client_for, template_csv):
    from api.schemas import ErrorResponse
    client = client_for(rate_limit=True, rate_limit_batch="1/minute", max_upload_bytes=1024 * 1024)
    assert post_batch(client, template_csv).status_code == 200
    limited = post_batch(client, template_csv)
    too_big = post_batch(TestClient(create_app(Settings(rate_limit=False, max_upload_bytes=1024 * 1024))),
                         b"a,b\n" + b"1,2\n" * 320_000)
    assert (limited.status_code, too_big.status_code) == (429, 413)
    for res in (limited, too_big):
        ErrorResponse.model_validate(res.json())

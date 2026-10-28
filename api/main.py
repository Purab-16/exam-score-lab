"""FastAPI service for the exam score model.

Run from the project root:
    uvicorn api.main:app --reload

Docs (development only): http://127.0.0.1:8000/docs
Settings and kill switches: see api/settings.py
"""
import hashlib
import io
import json
from contextlib import asynccontextmanager
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import sklearn
from fastapi import APIRouter, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.gzip import GZipMiddleware

from api.middleware import (
    BodySizeLimitMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware, multipart_limit,
)
from api.schemas import (
    BatchResponse, BatchSummary, ErrorResponse, InsightsResponse, Interval, MetaResponse, PredictResponse,
    Student, WhatIfRequest, WhatIfResponse,
)
from api.settings import Settings
from ml.insights import (
    DIET_ORDER, INTEGER_FEATURES, MAX_BATCH_ROWS, NUMERIC_HABITS, build_explainer, category_options,
    contributions_for, feature_ranges, interval, near_edge_features, suggest_tips,
    validate_batch, what_if,
)
from ml.paths import DATA_PATH, META_PATH, MODEL_PATH
from ml.pipeline import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET, predict_scores

LABELS = {
    "age": ("Age", "years"),
    "gender": ("Gender", ""),
    "study_hours_per_day": ("Study hours per day", "h"),
    "social_media_hours": ("Social media per day", "h"),
    "netflix_hours": ("Streaming per day", "h"),
    "part_time_job": ("Part-time job", ""),
    "attendance_percentage": ("Attendance", "%"),
    "sleep_hours": ("Sleep per night", "h"),
    "diet_quality": ("Diet quality", ""),
    "exercise_frequency": ("Exercise", "days/week"),
    "parental_education_level": ("Parental education", ""),
    "internet_quality": ("Internet quality", ""),
    "mental_health_rating": ("Mental health rating", "/10"),
    "extracurricular_participation": ("Extracurricular activities", ""),
}

# How long browsers may reuse /meta, /insights and /template.csv. They only change on retraining.
STATIC_MAX_AGE_SECONDS = 300


# ---------- data that is built once ----------

def _json_bytes(payload) -> bytes:
    # The same encoding FastAPI uses for a normal JSON response, so the output does not change
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _etag(body: bytes) -> str:
    return '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def _build_meta(meta, ranges, options):
    return {
        "model": {
            "name": meta.get("model"),
            "tuned": meta.get("tuned"),
            "trained_at": meta.get("trained_at"),
            "test_metrics": meta.get("test_metrics"),
            "interval": meta.get("interval"),
            "sklearn_version": meta.get("sklearn_version"),
            "sklearn_version_matches": meta.get("sklearn_version") == sklearn.__version__,
        },
        "features": FEATURES,
        "numeric": {
            c: {"label": LABELS[c][0], "unit": LABELS[c][1], "integer": c in INTEGER_FEATURES,
                "step": 1 if c in INTEGER_FEATURES else 0.1, **ranges[c]}
            for c in NUMERIC_FEATURES
        },
        "categorical": {c: {"label": LABELS[c][0], "options": options[c]} for c in CATEGORICAL_FEATURES},
        "habits": [{"feature": c, "label": LABELS[c][0]} for c in NUMERIC_HABITS] +
                  [{"feature": "diet_quality", "label": LABELS["diet_quality"][0]}],
        "diet_order": DIET_ORDER,
        "max_batch_rows": MAX_BATCH_ROWS,
    }


def _build_insights(model, data):
    actual = data[TARGET]
    preds = predict_scores(model, data[FEATURES])

    counts, edges = np.histogram(actual, bins=20, range=(0, 100))
    correlations = sorted(
        ({"feature": c, "label": LABELS[c][0], "r": round(float(np.corrcoef(data[c], actual)[0, 1]), 4)}
         for c in NUMERIC_FEATURES),
        key=lambda d: d["r"], reverse=True,
    )
    category_means = {
        c: [{"value": str(v), "mean": round(float(g.mean()), 2), "count": int(len(g))}
            for v, g in actual.groupby(data[c].fillna("Unknown"))]
        for c in CATEGORICAL_FEATURES
    }
    return {
        "count": int(len(data)),
        "summary": {"mean": round(float(actual.mean()), 2), "median": round(float(actual.median()), 2),
                    "std": round(float(actual.std()), 2), "min": float(actual.min()), "max": float(actual.max())},
        "histogram": [{"start": float(edges[i]), "end": float(edges[i + 1]), "count": int(counts[i])}
                      for i in range(len(counts))],
        "correlations": correlations,
        "category_means": category_means,
        "scatter": {c: [{"x": float(x), "y": float(y)} for x, y in zip(data[c], actual, strict=True)] for c in NUMERIC_FEATURES},
        "predicted_vs_actual": [{"actual": float(a), "predicted": round(float(p), 2)} for a, p in zip(actual, preds, strict=True)],
    }


@lru_cache(maxsize=2)
def load_resources(explainer_method: str = "auto") -> dict:
    """Model, data and the pre-built static responses. Loaded once per process, shared by every app."""
    model = joblib.load(MODEL_PATH)
    data = pd.read_csv(DATA_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
    ranges, options = feature_ranges(data), category_options(data)

    res = {
        "model": model, "data": data, "meta": meta, "ranges": ranges, "options": options,
        "explainer": build_explainer(model, data, explainer_method),
        "meta_body": _json_bytes(_build_meta(meta, ranges, options)),
        "insights_body": _json_bytes(_build_insights(model, data)),
        "template_body": data[["student_id"] + FEATURES].head(5).to_csv(index=False).encode("utf-8"),
    }
    for name in ("meta", "insights", "template"):
        res[f"{name}_etag"] = _etag(res[f"{name}_body"])
    return res


@asynccontextmanager
async def lifespan(app):
    app.state.resources = load_resources(app.state.settings.explainer)
    yield


# ---------- helpers ----------

def _interval(res, score):
    meta_interval = res["meta"].get("interval")
    if not meta_interval:
        return None
    low, high = interval(score, meta_interval["half_width"])
    return Interval(low=round(low, 2), high=round(high, 2), level=meta_interval["level"])


def _check_categories(res, values):
    errors = []
    for col, value in values.items():
        if col in CATEGORICAL_FEATURES and value not in res["options"][col]:
            errors.append(f"{col}: '{value}' is not one of {res['options'][col]}")
    if errors:
        raise HTTPException(status_code=422, detail=errors)


def _to_frame(res, student: Student):
    values = student.model_dump()
    _check_categories(res, values)
    return pd.DataFrame([values])[FEATURES]


def _etag_matches(header, etag: str) -> bool:
    if not header:
        return False
    for candidate in header.split(","):
        candidate = candidate.strip()
        if candidate == "*" or candidate.removeprefix("W/") == etag:
            return True
    return False


def _static_response(request: Request, body: bytes, etag: str, media_type: str, extra_headers=None):
    """A prebuilt response with cache headers and 304 support. Cache headers can be switched off."""
    headers = dict(extra_headers or {})
    if request.app.state.settings.cache_headers:
        cache_headers = {"ETag": etag, "Cache-Control": f"public, max-age={STATIC_MAX_AGE_SECONDS}"}
        if _etag_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=cache_headers)
        headers.update(cache_headers)
    return Response(content=body, media_type=media_type, headers=headers)


def _process_batch(res, content: bytes, max_bytes: int) -> BatchResponse:
    """The CPU-heavy part of a batch upload. Runs in a worker thread so the server stays responsive."""
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=[f"File is larger than {max_bytes / 1024 / 1024:g} MB."])
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=422, detail=[f"Could not read the file as CSV: {e}"]) from e

    X, errors, warnings = validate_batch(df, res["ranges"], res["options"])
    if errors:
        # Warnings are left out here: bad values also count as "empty", which reads as a second problem
        raise HTTPException(status_code=422, detail=errors)

    result = df.copy()
    scores = predict_scores(res["model"], X)
    result["predicted_score"] = np.round(scores, 2)
    half_width = res["meta"].get("interval", {}).get("half_width")
    if half_width:
        result["range_low"] = np.round(np.clip(scores - half_width, 0, 100), 2)
        result["range_high"] = np.round(np.clip(scores + half_width, 0, 100), 2)

    # NaN is not valid JSON, so empty cells are sent as null
    rows = json.loads(result.to_json(orient="records"))
    return BatchResponse(
        columns=list(result.columns),
        rows=rows,
        summary=BatchSummary(count=len(result), mean_score=round(float(scores.mean()), 2),
                             below_50=int((scores < 50).sum())),
        warnings=warnings,
    )


# ---------- routes ----------

router = APIRouter()

# Error answers, as shown in the API docs. They always look like {"detail": [...]}.
RATE_LIMITED = {429: {"model": ErrorResponse, "description": "Too many requests. See the Retry-After header."}}
REQUEST_ERRORS = {
    400: {"model": ErrorResponse, "description": "The request body could not be read, for example it is not valid text."},
    413: {"model": ErrorResponse, "description": "The request body is too large."},
    422: {"model": ErrorResponse, "description": "The request is not valid."},
    **RATE_LIMITED,
}


@router.get("/health")
def health(request: Request):
    return {"status": "ok", "model": request.app.state.resources["meta"].get("model", "unknown")}


# `responses` only documents the shape for the API docs. The answer is prebuilt JSON, not validated here.
@router.get("/meta", responses={200: {"model": MetaResponse}, **RATE_LIMITED})
def meta(request: Request):
    res = request.app.state.resources
    return _static_response(request, res["meta_body"], res["meta_etag"], "application/json")


@router.post("/predict", response_model=PredictResponse, responses=REQUEST_ERRORS)
def predict(student: Student, request: Request):
    res = request.app.state.resources
    row = _to_frame(res, student)
    score = what_if(res["model"], row, {})
    contributions = contributions_for(res["explainer"], row)
    tips = suggest_tips(res["model"], row, contributions, res["ranges"])
    return PredictResponse(
        score=round(score, 2),
        interval=_interval(res, score),
        edge_features=near_edge_features(row.iloc[0], res["ranges"]),
        tips=[{k: t[k] for k in ("feature", "label", "current", "suggested", "unit", "gain")} for t in tips],
    )


@router.post("/what-if", response_model=WhatIfResponse, responses=REQUEST_ERRORS)
def what_if_route(req: WhatIfRequest, request: Request):
    res = request.app.state.resources
    row = _to_frame(res, req.student)
    unknown = [c for c in req.changes if c not in FEATURES]
    if unknown:
        raise HTTPException(status_code=422, detail=[f"Unknown feature: {c}" for c in unknown])
    # Re-validate the changed profile with the same rules as /predict
    try:
        changed = Student(**{**req.student.model_dump(), **req.changes})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
                                                     for err in e.errors()]) from e
    _check_categories(res, changed.model_dump())

    base = what_if(res["model"], row, {})
    new = what_if(res["model"], row, {c: getattr(changed, c) for c in req.changes})
    return WhatIfResponse(base_score=round(base, 2), new_score=round(new, 2),
                          delta=round(new - base, 2), interval=_interval(res, new))


@router.post("/predict/batch", response_model=BatchResponse, responses=REQUEST_ERRORS)
async def predict_batch(request: Request, file: UploadFile = File(...)):
    res = request.app.state.resources
    max_bytes = request.app.state.settings.max_upload_bytes
    content = await file.read()
    return await run_in_threadpool(_process_batch, res, content, max_bytes)


@router.get("/template.csv", responses={200: {"content": {"text/csv": {"schema": {"type": "string"}}}}, **RATE_LIMITED})
def template_csv(request: Request):
    res = request.app.state.resources
    return _static_response(request, res["template_body"], res["template_etag"], "text/csv",
                            {"Content-Disposition": 'attachment; filename="students_template.csv"'})


@router.get("/insights", responses={200: {"model": InsightsResponse}, **RATE_LIMITED})
def insights(request: Request):
    res = request.app.state.resources
    return _static_response(request, res["insights_body"], res["insights_etag"], "application/json")


# ---------- app ----------

def create_app(settings: Settings = None) -> FastAPI:
    """Build the app. Tests pass their own settings. Production uses the environment."""
    settings = settings or Settings.from_env()
    rules = settings.rate_rules()
    docs = settings.docs_enabled

    app = FastAPI(
        title="Student Exam Score API", version="1.0.0", lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings

    # The last middleware added is the outermost. CORS is outermost so that 413 and 429 errors
    # still carry CORS headers and the browser can show the real message.
    if settings.body_limit:
        app.add_middleware(
            BodySizeLimitMiddleware,
            default_limit=settings.max_json_body_bytes,
            path_limits={"/predict/batch": multipart_limit(settings.max_upload_bytes)},
        )
    if settings.rate_limit:
        app.add_middleware(RateLimitMiddleware, rules=rules, exempt_paths=("/health",))
    if settings.security_headers:
        app.add_middleware(SecurityHeadersMiddleware, csp_skip_paths=("/docs", "/redoc") if docs else ())
    if settings.gzip:
        app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()

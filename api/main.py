"""FastAPI service for the exam score model.

Run from the project root:
    uvicorn api.main:app --reload

Docs: http://127.0.0.1:8000/docs
"""
import io
import json
import os
from contextlib import asynccontextmanager

import joblib
import numpy as np
import pandas as pd
import sklearn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from api.schemas import (
    BatchResponse, BatchSummary, Interval, PredictResponse, Student, WhatIfRequest, WhatIfResponse,
)
from ml.insights import (
    DIET_ORDER, INTEGER_FEATURES, MAX_BATCH_ROWS, NUMERIC_HABITS, build_explainer, category_options,
    contributions_for, feature_ranges, interval, near_edge_features, suggest_tips,
    validate_batch, what_if,
)
from ml.paths import DATA_PATH, META_PATH, MODEL_PATH
from ml.pipeline import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, TARGET, predict_scores

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

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

state = {}


def _cors_origins():
    raw = os.getenv("API_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app):
    model = joblib.load(MODEL_PATH)
    data = pd.read_csv(DATA_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
    state.update(
        model=model,
        data=data,
        meta=meta,
        ranges=feature_ranges(data),
        options=category_options(data),
        shap_ctx=build_explainer(model, data),
        insights=_build_insights(model, data),
    )
    yield
    state.clear()


app = FastAPI(title="Student Exam Score API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def _interval(score):
    meta_interval = state["meta"].get("interval")
    if not meta_interval:
        return None
    low, high = interval(score, meta_interval["half_width"])
    return Interval(low=round(low, 2), high=round(high, 2), level=meta_interval["level"])


def _check_categories(values):
    errors = []
    for col, value in values.items():
        if col in CATEGORICAL_FEATURES and value not in state["options"][col]:
            errors.append(f"{col}: '{value}' is not one of {state['options'][col]}")
    if errors:
        raise HTTPException(status_code=422, detail=errors)


def _to_frame(student: Student):
    values = student.model_dump()
    _check_categories(values)
    return pd.DataFrame([values])[FEATURES]


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
        "scatter": {c: [{"x": float(x), "y": float(y)} for x, y in zip(data[c], actual)] for c in NUMERIC_FEATURES},
        "predicted_vs_actual": [{"actual": float(a), "predicted": round(float(p), 2)} for a, p in zip(actual, preds)],
    }


# ---------- routes ----------

@app.get("/health")
def health():
    return {"status": "ok", "model": state["meta"].get("model", "unknown")}


@app.get("/meta")
def meta():
    m = state["meta"]
    ranges = state["ranges"]
    return {
        "model": {
            "name": m.get("model"),
            "tuned": m.get("tuned"),
            "trained_at": m.get("trained_at"),
            "test_metrics": m.get("test_metrics"),
            "interval": m.get("interval"),
            "sklearn_version": m.get("sklearn_version"),
            "sklearn_version_matches": m.get("sklearn_version") == sklearn.__version__,
        },
        "features": FEATURES,
        "numeric": {
            c: {"label": LABELS[c][0], "unit": LABELS[c][1], "integer": c in INTEGER_FEATURES,
                "step": 1 if c in INTEGER_FEATURES else 0.1, **ranges[c]}
            for c in NUMERIC_FEATURES
        },
        "categorical": {c: {"label": LABELS[c][0], "options": state["options"][c]} for c in CATEGORICAL_FEATURES},
        "habits": [{"feature": c, "label": LABELS[c][0]} for c in NUMERIC_HABITS] +
                  [{"feature": "diet_quality", "label": LABELS["diet_quality"][0]}],
        "diet_order": DIET_ORDER,
        "max_batch_rows": MAX_BATCH_ROWS,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(student: Student):
    row = _to_frame(student)
    score = what_if(state["model"], row, {})
    contributions = contributions_for(state["shap_ctx"], row)
    tips = suggest_tips(state["model"], row, contributions, state["ranges"])
    return PredictResponse(
        score=round(score, 2),
        interval=_interval(score),
        edge_features=near_edge_features(row.iloc[0], state["ranges"]),
        tips=[{k: t[k] for k in ("feature", "label", "current", "suggested", "unit", "gain")} for t in tips],
    )


@app.post("/what-if", response_model=WhatIfResponse)
def what_if_route(req: WhatIfRequest):
    row = _to_frame(req.student)
    unknown = [c for c in req.changes if c not in FEATURES]
    if unknown:
        raise HTTPException(status_code=422, detail=[f"Unknown feature: {c}" for c in unknown])
    # Re-validate the changed profile with the same rules as /predict
    try:
        changed = Student(**{**req.student.model_dump(), **req.changes})
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
                                                     for err in e.errors()])
    _check_categories(changed.model_dump())

    base = what_if(state["model"], row, {})
    new = what_if(state["model"], row, {c: getattr(changed, c) for c in req.changes})
    return WhatIfResponse(base_score=round(base, 2), new_score=round(new, 2),
                          delta=round(new - base, 2), interval=_interval(new))


@app.post("/predict/batch", response_model=BatchResponse)
async def predict_batch(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=["File is larger than 5 MB."])
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=422, detail=[f"Could not read the file as CSV: {e}"])

    X, errors, warnings = validate_batch(df, state["ranges"], state["options"])
    if errors:
        # Warnings are left out here: bad values also count as "empty", which reads as a second problem
        raise HTTPException(status_code=422, detail=errors)

    result = df.copy()
    scores = predict_scores(state["model"], X)
    result["predicted_score"] = np.round(scores, 2)
    half_width = state["meta"].get("interval", {}).get("half_width")
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


@app.get("/template.csv", response_class=PlainTextResponse)
def template_csv():
    sample = state["data"][["student_id"] + FEATURES].head(5)
    return PlainTextResponse(sample.to_csv(index=False), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="students_template.csv"'})


@app.get("/insights")
def insights():
    return state["insights"]

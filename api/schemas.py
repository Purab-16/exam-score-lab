"""Request and response models for the API."""
import os
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Unknown fields in a request give a 422, and so do true/false or text in a number field.
# Set STRICT_INPUT=false to go back to ignoring unknown fields and converting such values.
# Read once at import time, because it shapes the models.
_STRICT = os.getenv("STRICT_INPUT", "true").strip().lower() not in ("0", "false", "no", "off")
_EXTRA = "forbid" if _STRICT else "ignore"

# Longest text accepted for a category value. The real options are all under 20 characters.
_TEXT = 40


def _number(value):
    """A number field must receive a number. By default pydantic quietly turns true into 1.0 and
    "3.5" into 3.5, so a client bug would give a plausible-looking score. JSON numbers like 20.0 for a
    whole-number field are still fine."""
    if _STRICT and isinstance(value, (bool, str)):
        raise ValueError("must be a number")
    return value


Count = Annotated[int, BeforeValidator(_number)]
Amount = Annotated[float, BeforeValidator(_number)]


def _not_boolean(value):
    """A new value for a what-if change is a number or text. true and false would become 1.0 and 0.0."""
    if _STRICT and isinstance(value, bool):
        raise ValueError("must be a number or text, not true or false")
    return value


ChangeValue = Annotated[Union[float, str], BeforeValidator(_not_boolean)]

# The model's input columns. A test keeps this list equal to ml.pipeline.FEATURES, and the web app's
# generated types use it, so a renamed column is caught at build time instead of in the browser.
FeatureName = Literal[
    "age", "gender", "study_hours_per_day", "social_media_hours", "netflix_hours", "part_time_job",
    "attendance_percentage", "sleep_hours", "diet_quality", "exercise_frequency",
    "parental_education_level", "internet_quality", "mental_health_rating", "extracurricular_participation",
]


class Student(BaseModel):
    """One student's profile. Categorical values must match GET /meta options."""

    model_config = ConfigDict(extra=_EXTRA, json_schema_extra={"example": {
        "age": 20, "gender": "Female", "study_hours_per_day": 3.5, "social_media_hours": 2.5,
        "netflix_hours": 1.8, "part_time_job": "No", "attendance_percentage": 84.0,
        "sleep_hours": 6.5, "diet_quality": "Fair", "exercise_frequency": 3,
        "parental_education_level": "Bachelor", "internet_quality": "Average",
        "mental_health_rating": 5, "extracurricular_participation": "No",
    }})

    age: Count = Field(ge=10, le=100)
    gender: str = Field(max_length=_TEXT)
    study_hours_per_day: Amount = Field(ge=0, le=24, allow_inf_nan=False)
    social_media_hours: Amount = Field(ge=0, le=24, allow_inf_nan=False)
    netflix_hours: Amount = Field(ge=0, le=24, allow_inf_nan=False)
    part_time_job: str = Field(max_length=_TEXT)
    attendance_percentage: Amount = Field(ge=0, le=100, allow_inf_nan=False)
    sleep_hours: Amount = Field(ge=0, le=24, allow_inf_nan=False)
    diet_quality: str = Field(max_length=_TEXT)
    exercise_frequency: Count = Field(ge=0, le=7)
    parental_education_level: str = Field(max_length=_TEXT)
    internet_quality: str = Field(max_length=_TEXT)
    mental_health_rating: Count = Field(ge=1, le=10)
    extracurricular_participation: str = Field(max_length=_TEXT)


class Interval(BaseModel):
    low: float
    high: float
    level: float


class Tip(BaseModel):
    feature: FeatureName
    label: str
    current: Union[float, str]
    suggested: Union[float, str]
    unit: str
    gain: float


class PredictResponse(BaseModel):
    score: float
    interval: Optional[Interval]
    edge_features: list[FeatureName]
    tips: list[Tip]


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra=_EXTRA)

    student: Student
    changes: dict[str, ChangeValue] = Field(
        max_length=14,
        description="Feature name to new value, e.g. {\"study_hours_per_day\": 5}",
    )


class WhatIfResponse(BaseModel):
    base_score: float
    new_score: float
    delta: float
    interval: Optional[Interval]


class BatchSummary(BaseModel):
    count: int
    mean_score: float
    below_50: int


class BatchResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    summary: BatchSummary
    warnings: list[str]


# ---------- GET /meta and GET /insights ----------
# These two answers are built once at startup and sent as ready-made JSON, so these models do not
# produce them. They describe the shape for the API docs and for the web app's generated types.
# A test checks that the real answers still match, and forbids undocumented fields.

class _Documented(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NumericSpec(_Documented):
    label: str
    unit: str
    integer: bool
    step: float
    min: float
    max: float
    median: float


class CategoricalSpec(_Documented):
    label: str
    options: list[str]


class HabitSpec(_Documented):
    feature: FeatureName
    label: str


class TestMetrics(_Documented):
    __test__ = False  # not a pytest class, despite the name

    rmse: float
    r2: float
    interval_coverage: float
    clipped_predictions: int


class IntervalInfo(_Documented):
    level: float
    half_width: float


class ModelInfo(_Documented):
    name: Optional[str]
    tuned: Optional[bool]
    trained_at: Optional[str]
    test_metrics: Optional[TestMetrics]
    interval: Optional[IntervalInfo]
    sklearn_version: Optional[str]
    sklearn_version_matches: bool


class MetaResponse(_Documented):
    model: ModelInfo
    features: list[FeatureName]
    numeric: dict[str, NumericSpec]
    categorical: dict[str, CategoricalSpec]
    habits: list[HabitSpec]
    diet_order: list[str]
    max_batch_rows: int


class ScoreSummary(_Documented):
    mean: float
    median: float
    std: float
    min: float
    max: float


class HistogramBin(_Documented):
    start: float
    end: float
    count: int


class Correlation(_Documented):
    feature: FeatureName
    label: str
    r: float


class CategoryMean(_Documented):
    value: str
    mean: float
    count: int


class Point(_Documented):
    x: float
    y: float


class PredictedActual(_Documented):
    actual: float
    predicted: float


class InsightsResponse(_Documented):
    count: int
    summary: ScoreSummary
    histogram: list[HistogramBin]
    correlations: list[Correlation]
    category_means: dict[str, list[CategoryMean]]
    scatter: dict[str, list[Point]]
    predicted_vs_actual: list[PredictedActual]


# ---------- error answers ----------
# Every error answer is {"detail": ...}. `detail` is a list of plain messages (our own checks, the size
# and rate limits) or of details about a field (a field check done by FastAPI). A few answers made by
# FastAPI itself, such as "Not Found" and "There was an error parsing the body", use a single text.

class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="allow")  # FastAPI adds `input`, `ctx` and a documentation `url`

    type: str
    loc: list[Union[str, int]]
    msg: str
    input: Optional[Any] = None


class ErrorResponse(BaseModel):
    detail: Union[str, list[Union[str, ValidationIssue]]]

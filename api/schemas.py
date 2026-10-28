"""Request and response models for the API."""
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class Student(BaseModel):
    """One student's profile. Categorical values must match GET /meta options."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "age": 20, "gender": "Female", "study_hours_per_day": 3.5, "social_media_hours": 2.5,
        "netflix_hours": 1.8, "part_time_job": "No", "attendance_percentage": 84.0,
        "sleep_hours": 6.5, "diet_quality": "Fair", "exercise_frequency": 3,
        "parental_education_level": "Bachelor", "internet_quality": "Average",
        "mental_health_rating": 5, "extracurricular_participation": "No",
    }})

    age: int = Field(ge=10, le=100)
    gender: str
    study_hours_per_day: float = Field(ge=0, le=24, allow_inf_nan=False)
    social_media_hours: float = Field(ge=0, le=24, allow_inf_nan=False)
    netflix_hours: float = Field(ge=0, le=24, allow_inf_nan=False)
    part_time_job: str
    attendance_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    sleep_hours: float = Field(ge=0, le=24, allow_inf_nan=False)
    diet_quality: str
    exercise_frequency: int = Field(ge=0, le=7)
    parental_education_level: str
    internet_quality: str
    mental_health_rating: int = Field(ge=1, le=10)
    extracurricular_participation: str


class Interval(BaseModel):
    low: float
    high: float
    level: float


class Tip(BaseModel):
    feature: str
    label: str
    current: Union[float, str]
    suggested: Union[float, str]
    unit: str
    gain: float


class PredictResponse(BaseModel):
    score: float
    interval: Optional[Interval]
    edge_features: list[str]
    tips: list[Tip]


class WhatIfRequest(BaseModel):
    student: Student
    changes: dict[str, Union[float, str]] = Field(
        description="Feature name to new value, e.g. {\"study_hours_per_day\": 5}"
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

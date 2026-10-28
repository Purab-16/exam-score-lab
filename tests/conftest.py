import json
import os
from pathlib import Path

# The shared app in api.main is used by many tests. Without this, the per-client rate limit would
# make a long test run fail. Rate limiting has its own tests, which build their own app.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import joblib
import pandas as pd
import pytest

from ml.insights import category_options, feature_ranges
from ml.paths import DATA_PATH, META_PATH, MODEL_PATH

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def data():
    return pd.read_csv(DATA_PATH)


@pytest.fixture(scope="session")
def model():
    return joblib.load(MODEL_PATH)


@pytest.fixture(scope="session")
def meta():
    return json.loads(META_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def ranges(data):
    return feature_ranges(data)


@pytest.fixture(scope="session")
def options(data):
    return category_options(data)


@pytest.fixture
def student():
    """An average student, as the app would send it."""
    return pd.DataFrame([{
        "age": 20, "gender": "Female", "study_hours_per_day": 3.5, "social_media_hours": 2.5,
        "netflix_hours": 1.8, "part_time_job": "No", "attendance_percentage": 84.0,
        "sleep_hours": 6.5, "diet_quality": "Fair", "exercise_frequency": 3,
        "parental_education_level": "Bachelor", "internet_quality": "Average",
        "mental_health_rating": 5, "extracurricular_participation": "No",
    }])


@pytest.fixture
def weak_student(student):
    """A student with several habits that pull the score down."""
    s = student.copy()
    s[["study_hours_per_day", "social_media_hours", "sleep_hours", "diet_quality"]] = [1.0, 5.0, 5.0, "Poor"]
    return s

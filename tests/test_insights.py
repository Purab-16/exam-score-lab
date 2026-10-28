import numpy as np
import pandas as pd
import pytest

from ml.insights import (
    DIET_ORDER, interval, near_edge_features, shap_by_feature, suggest_tips, validate_batch, what_if,
)
from ml.pipeline import FEATURES


def test_ranges_cover_training_data(ranges, data):
    assert ranges["study_hours_per_day"]["min"] == data["study_hours_per_day"].min()
    assert ranges["attendance_percentage"]["max"] == data["attendance_percentage"].max()


def test_category_options(options):
    assert options["diet_quality"] == DIET_ORDER
    assert "Unknown" in options["parental_education_level"]
    assert "Unknown" not in options["gender"]


def test_near_edge_features(ranges, student):
    row = student.iloc[0].copy()
    assert near_edge_features(row, ranges) == []
    row["study_hours_per_day"] = ranges["study_hours_per_day"]["max"]
    assert near_edge_features(row, ranges) == ["study_hours_per_day"]


@pytest.mark.parametrize("score,expected", [(50, (41.4, 58.6)), (3, (0.0, 11.6)), (97, (88.4, 100.0))])
def test_interval_is_clipped(score, expected):
    low, high = interval(score, 8.6)
    assert (low, high) == pytest.approx(expected)


def test_what_if_without_changes_matches_prediction(model, student):
    assert what_if(model, student, {}) == pytest.approx(float(np.clip(model.predict(student)[0], 0, 100)))


def test_what_if_more_study_raises_score(model, student):
    assert what_if(model, student, {"study_hours_per_day": 5.5}) > what_if(model, student, {})


def test_what_if_does_not_modify_input(model, student):
    before = student.copy()
    what_if(model, student, {"study_hours_per_day": 6.0})
    pd.testing.assert_frame_equal(student, before)


def test_shap_by_feature_sums_one_hot_levels():
    names = ["num__age", "cat__diet_quality_Fair", "cat__diet_quality_Poor", "cat__gender_Male"]
    totals = shap_by_feature([1.0, -2.0, 0.5, 0.25], names)
    assert totals == {"age": 1.0, "diet_quality": -1.5, "gender": 0.25}


def test_tips_for_weak_student(model, weak_student, ranges):
    contributions = {"study_hours_per_day": -5.0, "social_media_hours": -2.0,
                     "sleep_hours": -1.0, "diet_quality": -0.5, "netflix_hours": 0.3}
    tips = suggest_tips(model, weak_student, contributions, ranges)

    assert 1 <= len(tips) <= 3
    assert tips[0]["feature"] == "study_hours_per_day"
    assert all(t["gain"] > 0 for t in tips)
    assert [t["gain"] for t in tips] == sorted((t["gain"] for t in tips), reverse=True)
    # Features that are not pulling the score down are never suggested
    assert "netflix_hours" not in {t["feature"] for t in tips}


def test_tips_respect_data_range(model, weak_student, ranges):
    weak_student["study_hours_per_day"] = ranges["study_hours_per_day"]["max"]
    tips = suggest_tips(model, weak_student, {"study_hours_per_day": -1.0}, ranges)
    assert tips == []


def test_no_tips_when_nothing_pulls_down(model, student, ranges):
    assert suggest_tips(model, student, {"study_hours_per_day": 2.0}, ranges) == []


# --- batch CSV validation ---

@pytest.fixture
def batch(data):
    return data.drop(columns=["exam_score"]).head(20).reset_index(drop=True)


def test_valid_batch(batch, ranges, options):
    X, errors, warnings = validate_batch(batch, ranges, options)
    assert errors == []
    assert list(X.columns) == FEATURES
    assert len(X) == len(batch)


def test_batch_missing_columns(batch, ranges, options):
    X, errors, _ = validate_batch(batch.drop(columns=["age", "gender"]), ranges, options)
    assert X is None
    assert errors == ["Missing columns: age, gender"]


def test_batch_empty(batch, ranges, options):
    X, errors, _ = validate_batch(batch.head(0), ranges, options)
    assert X is None and errors == ["The file has no rows."]


def test_batch_bad_values_report_spreadsheet_rows(batch, ranges, options):
    bad = batch.astype(object)
    bad.loc[0, "age"] = "twenty"
    bad.loc[3, "diet_quality"] = "Excellent"
    X, errors, _ = validate_batch(bad, ranges, options)
    assert X is None
    assert any("`age`" in e and "rows 2" in e for e in errors)
    assert any("Excellent" in e and "rows 5" in e for e in errors)


def test_batch_out_of_range_is_a_warning(batch, ranges, options):
    batch.loc[0, "study_hours_per_day"] = 15
    X, errors, warnings = validate_batch(batch, ranges, options)
    assert X is not None and errors == []
    assert any("study_hours_per_day" in w and "1 row." in w for w in warnings)


def test_batch_trims_and_imputes_categories(batch, ranges, options, model):
    batch.loc[0, "diet_quality"] = "  Good "
    batch.loc[1, "gender"] = None
    X, errors, warnings = validate_batch(batch, ranges, options)
    assert errors == []
    assert X.loc[0, "diet_quality"] == "Good"
    assert pd.isna(X.loc[1, "gender"])
    assert np.isfinite(model.predict(X)).all()

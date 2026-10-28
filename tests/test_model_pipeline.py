import numpy as np
import pytest
from sklearn.linear_model import Ridge

from ml.pipeline import ENGINEERED_FEATURES, FEATURES, TARGET, add_engineered_features, build_pipeline, predict_scores


def test_engineered_features_values(student):
    out = add_engineered_features(student)
    row = out.iloc[0]
    assert row["total_screen_time"] == pytest.approx(2.5 + 1.8)
    assert row["study_to_sleep_ratio"] == pytest.approx(3.5 / 6.5)
    assert row["study_x_attendance"] == pytest.approx(3.5 * 0.84)
    # Input is not modified
    assert "total_screen_time" not in student.columns


def test_engineered_features_zero_sleep_is_safe(student):
    student["sleep_hours"] = 0.0
    out = add_engineered_features(student)
    assert np.isfinite(out["study_to_sleep_ratio"]).all()


@pytest.mark.parametrize("engineered", [False, True])
def test_pipeline_fits_with_missing_values(data, engineered):
    pipe = build_pipeline(Ridge(), engineered=engineered).fit(data[FEATURES], data[TARGET])
    names = list(pipe[:-1].get_feature_names_out())
    assert any("parental_education_level_Unknown" in n for n in names)
    assert all(any(f in n for n in names) for f in ENGINEERED_FEATURES) == engineered
    assert pipe.predict(data[FEATURES].head(3)).shape == (3,)


def test_predict_scores_clips_to_valid_range(model, student):
    extreme = student.copy()
    extreme[["study_hours_per_day", "attendance_percentage", "mental_health_rating"]] = [8.3, 100.0, 10]
    low = student.copy()
    low[["study_hours_per_day", "attendance_percentage", "mental_health_rating"]] = [0.0, 56.0, 1]
    assert model.predict(extreme)[0] > 100 or model.predict(low)[0] < 0, "test needs an out-of-range raw prediction"
    for row in (extreme, low):
        assert 0.0 <= predict_scores(model, row)[0] <= 100.0

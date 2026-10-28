"""Shared model code used by train.py and the API.

Keep this module importable as `ml.pipeline`: when engineered features are enabled, the saved model
(models/best_model.pkl) references add_engineered_features by this module path, so joblib needs it
to load the model. Renaming or moving this file means retraining with `python train.py`.
"""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

TARGET = "exam_score"
SCORE_MIN, SCORE_MAX = 0.0, 100.0

NUMERIC_FEATURES = [
    "age", "study_hours_per_day", "social_media_hours", "netflix_hours",
    "attendance_percentage", "sleep_hours", "exercise_frequency",
    "mental_health_rating",
]
CATEGORICAL_FEATURES = [
    "gender", "part_time_job", "diet_quality", "parental_education_level",
    "internet_quality", "extracurricular_participation",
]
# Same column order the app sends to the model
FEATURES = [
    "age", "gender", "study_hours_per_day", "social_media_hours", "netflix_hours",
    "part_time_job", "attendance_percentage", "sleep_hours", "diet_quality",
    "exercise_frequency", "parental_education_level", "internet_quality",
    "mental_health_rating", "extracurricular_participation",
]
ENGINEERED_FEATURES = ["total_screen_time", "study_to_sleep_ratio", "study_x_attendance"]


def add_engineered_features(X):
    X = X.copy()
    X["total_screen_time"] = X["social_media_hours"] + X["netflix_hours"]
    # Guard against zero sleep coming from the app sliders
    X["study_to_sleep_ratio"] = X["study_hours_per_day"] / X["sleep_hours"].clip(lower=1.0)
    X["study_x_attendance"] = X["study_hours_per_day"] * X["attendance_percentage"] / 100.0
    return X


def _engineered_feature_names(transformer, input_features):
    return np.asarray(list(input_features) + ENGINEERED_FEATURES, dtype=object)


def build_pipeline(regressor, engineered=False):
    """Preprocessing + regressor. The last step is always named 'regressor'."""
    numeric = NUMERIC_FEATURES + (ENGINEERED_FEATURES if engineered else [])

    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    # Missing categories become their own "Unknown" level instead of the mode
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    preprocessor = ColumnTransformer([
        ("num", numeric_transformer, numeric),
        ("cat", categorical_transformer, CATEGORICAL_FEATURES),
    ])

    steps = []
    if engineered:
        steps.append(("features", FunctionTransformer(
            add_engineered_features, feature_names_out=_engineered_feature_names
        )))
    steps += [("preprocessor", preprocessor), ("regressor", regressor)]
    return Pipeline(steps)


def predict_scores(model, X):
    """Predict exam scores clipped to the valid 0 to 100 range."""
    return np.clip(model.predict(X), SCORE_MIN, SCORE_MAX)

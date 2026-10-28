"""Prediction logic behind the API: input ranges, what-if, tips, SHAP contributions, batch validation."""
import numpy as np
import pandas as pd

from ml.pipeline import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, SCORE_MAX, SCORE_MIN, predict_scores

INTEGER_FEATURES = ["age", "exercise_frequency", "mental_health_rating"]
EDGE_FRACTION = 0.05
MAX_BATCH_ROWS = 10_000

# Habits a student can change, with the suggested step and how to phrase it
NUMERIC_HABITS = {
    "study_hours_per_day": {"step": 1.0, "label": "Study 1 more hour per day", "unit": "h"},
    "social_media_hours": {"step": -1.0, "label": "Spend 1 hour less on social media", "unit": "h"},
    "netflix_hours": {"step": -1.0, "label": "Spend 1 hour less on streaming", "unit": "h"},
    "attendance_percentage": {"step": 5.0, "label": "Attend 5% more classes", "unit": "%"},
    "exercise_frequency": {"step": 1.0, "label": "Exercise 1 more day per week", "unit": " days"},
    "sleep_hours": {"label": "Move sleep towards 7 to 9 hours", "unit": "h"},
}
DIET_ORDER = ["Poor", "Fair", "Good"]


def pretty(name):
    return name.replace("_", " ").title()


def feature_ranges(data):
    """Min, max and median of each numeric feature in the training data."""
    return {
        col: {"min": float(data[col].min()), "max": float(data[col].max()), "median": float(data[col].median())}
        for col in NUMERIC_FEATURES
    }


def category_options(data):
    """Allowed values per categorical feature. 'Unknown' is always allowed (missing values become it)."""
    options = {}
    for col in CATEGORICAL_FEATURES:
        values = sorted(data[col].dropna().unique().tolist())
        if col == "diet_quality":
            values = [v for v in DIET_ORDER if v in values]
        options[col] = values + (["Unknown"] if col == "parental_education_level" else [])
    return options


def near_edge_features(row, ranges, fraction=EDGE_FRACTION):
    """Numeric inputs within `fraction` of the training min or max, where predictions are less reliable."""
    flagged = []
    for col, r in ranges.items():
        span = r["max"] - r["min"]
        value = float(row[col])
        if span > 0 and (value <= r["min"] + fraction * span or value >= r["max"] - fraction * span):
            flagged.append(col)
    return flagged


def interval(score, half_width):
    """Prediction interval clipped to the valid score range."""
    return max(SCORE_MIN, score - half_width), min(SCORE_MAX, score + half_width)


def what_if(model, row, changes):
    """Predicted score for `row` (a one-row DataFrame) after applying `changes`."""
    changed = row.copy()
    for col, value in changes.items():
        changed[col] = value
    return float(predict_scores(model, changed[FEATURES])[0])


def shap_by_feature(values, transformed_names):
    """Sum SHAP values of transformed columns (e.g. one-hot levels) back to the original feature."""
    totals = {}
    for value, name in zip(values, transformed_names):
        raw = name.split("__", 1)[-1]
        feature = next((c for c in CATEGORICAL_FEATURES if raw.startswith(c + "_")), raw)
        totals[feature] = totals.get(feature, 0.0) + float(value)
    return totals


def build_explainer(model, data):
    """SHAP explainer for the model's final estimator, plus what is needed to explain new rows."""
    import shap

    preprocessor = model[:-1]
    estimator = model.named_steps["regressor"]
    background = preprocessor.transform(data[FEATURES])

    if (hasattr(estimator, "tree_") or hasattr(estimator, "estimators_")
            or hasattr(estimator, "get_booster") or hasattr(estimator, "booster_")):
        explainer = shap.TreeExplainer(estimator)
    elif hasattr(estimator, "coef_"):
        explainer = shap.LinearExplainer(estimator, background)
    else:
        explainer = shap.Explainer(estimator, background)

    return {"preprocessor": preprocessor, "explainer": explainer,
            "names": list(preprocessor.get_feature_names_out())}


def contributions_for(shap_ctx, row):
    """SHAP value per original feature for a one-row DataFrame."""
    values = shap_ctx["explainer"](shap_ctx["preprocessor"].transform(row[FEATURES])).values[0]
    return shap_by_feature(values, shap_ctx["names"])


def _suggested_value(col, current, ranges):
    r = ranges[col]
    if col == "sleep_hours":
        if current < 7:
            target = min(current + 1.0, 9.0)
        elif current > 9:
            target = max(current - 1.0, 7.0)
        else:
            return None
    else:
        target = current + NUMERIC_HABITS[col]["step"]
    target = float(np.clip(target, r["min"], r["max"]))
    if col in INTEGER_FEATURES:
        target = float(round(target))
    return None if abs(target - current) < 1e-9 else target


def suggest_tips(model, row, contributions, ranges, top_n=3):
    """Habits that pull the score down (negative SHAP), with a suggested change and its predicted gain.

    `contributions` maps original feature name to its SHAP value (see shap_by_feature).
    """
    base_score = what_if(model, row, {})
    tips = []

    for col, cfg in NUMERIC_HABITS.items():
        if contributions.get(col, 0.0) >= 0:
            continue
        current = float(row[col].iloc[0])
        target = _suggested_value(col, current, ranges)
        if target is None:
            continue
        gain = what_if(model, row, {col: target}) - base_score
        if gain > 0:
            tips.append({
                "feature": col, "label": cfg["label"], "current": current, "suggested": target,
                "unit": cfg["unit"], "gain": gain, "shap": contributions[col],
            })

    diet = row["diet_quality"].iloc[0]
    if contributions.get("diet_quality", 0.0) < 0 and diet in DIET_ORDER[:-1]:
        better = DIET_ORDER[DIET_ORDER.index(diet) + 1]
        gain = what_if(model, row, {"diet_quality": better}) - base_score
        if gain > 0:
            tips.append({
                "feature": "diet_quality", "label": f"Improve diet from {diet} to {better}",
                "current": diet, "suggested": better, "unit": "", "gain": gain,
                "shap": contributions["diet_quality"],
            })

    return sorted(tips, key=lambda t: t["gain"], reverse=True)[:top_n]


def validate_batch(df, ranges, options):
    """Check an uploaded CSV. Returns (clean_features_or_None, errors, warnings)."""
    errors, warnings = [], []

    if len(df) == 0:
        return None, ["The file has no rows."], warnings
    if len(df) > MAX_BATCH_ROWS:
        return None, [f"The file has {len(df):,} rows. The limit is {MAX_BATCH_ROWS:,}."], warnings

    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        return None, [f"Missing columns: {', '.join(missing)}"], warnings

    X = df[FEATURES].copy()

    for col in NUMERIC_FEATURES:
        original = X[col]
        X[col] = pd.to_numeric(original, errors="coerce")
        bad = original.notna() & X[col].isna()
        if bad.any():
            errors.append(f"`{col}` has non-numeric values in rows {_row_list(bad)}.")
        r = ranges[col]
        outside = X[col].notna() & ((X[col] < r["min"]) | (X[col] > r["max"]))
        if outside.any():
            warnings.append(
                f"`{col}` is outside the training range ({r['min']:g} to {r['max']:g}) "
                f"in {_rows(int(outside.sum()))}. Those predictions are less reliable."
            )

    for col in CATEGORICAL_FEATURES:
        X[col] = X[col].astype("string").str.strip()
        bad = X[col].notna() & ~X[col].isin(options[col])
        if bad.any():
            errors.append(
                f"`{col}` has unknown values {sorted(X.loc[bad, col].unique().tolist())} in rows {_row_list(bad)}. "
                f"Allowed: {', '.join(options[col])}."
            )
        X[col] = X[col].astype(object).where(X[col].notna(), np.nan)

    n_missing = int(X.isna().any(axis=1).sum())
    if n_missing:
        warnings.append(f"{_rows(n_missing)} {'has' if n_missing == 1 else 'have'} empty values. "
                        "They will be filled the same way as in training.")

    return (None if errors else X), errors, warnings


def _rows(n):
    return f"{n} row" if n == 1 else f"{n} rows"


def _row_list(mask, limit=5):
    # Row numbers as a user sees them in a spreadsheet (header is row 1)
    rows = (np.flatnonzero(mask.to_numpy()) + 2).tolist()
    text = ", ".join(map(str, rows[:limit]))
    return text + (f" and {len(rows) - limit} more" if len(rows) > limit else "")

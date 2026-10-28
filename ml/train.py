"""Train the exam score model and save it for the API.

Steps:
    1. Split data into train and a held-out test set.
    2. 5-fold CV on the train set for 6 models, with and without engineered features.
    3. Tune the top 2 models with Optuna (CV on the train set only).
    4. Pick the best by CV RMSE and evaluate it once on the test set.
    5. Build a 90% prediction interval from out-of-fold residuals.
    6. Refit on all rows and save the model and metadata.

Every run is logged to MLflow (local mlflow.db + mlruns/).

Usage (from the project root):
    python train.py [--trials 30] [--no-mlflow]
    python -m ml.train [--trials 30] [--no-mlflow]

Outputs (in models/):
    best_model.pkl   - fitted scikit-learn pipeline
    model_meta.json  - library versions, CV results, test metrics, interval width
"""
import argparse
import json
import platform
import warnings
from datetime import datetime, timezone

import joblib
import lightgbm
import numpy as np
import optuna
import pandas as pd
import sklearn
import xgboost
from lightgbm import LGBMRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, cross_validate, train_test_split
from xgboost import XGBRegressor

from ml.paths import DATA_PATH, META_PATH, MLFLOW_DB_PATH, MODEL_DIR, MODEL_PATH
from ml.pipeline import FEATURES, TARGET, build_pipeline, predict_scores

MLFLOW_URI = f"sqlite:///{MLFLOW_DB_PATH.as_posix()}"

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
INTERVAL_LEVEL = 0.90
TOP_K_TO_TUNE = 2
# Engineered features are kept only if they beat base features by at least this much CV RMSE
MIN_FEATURE_GAIN = 0.01

warnings.filterwarnings("ignore", message="X does not have valid feature names")
optuna.logging.set_verbosity(optuna.logging.WARNING)


def make_regressor(name, params=None):
    params = params or {}
    if name == "linear_regression":
        return LinearRegression()
    if name == "ridge":
        return Ridge(**{"alpha": 1.0, **params})
    if name == "random_forest":
        return RandomForestRegressor(**{"n_estimators": 300, "random_state": RANDOM_STATE, "n_jobs": -1, **params})
    if name == "gradient_boosting":
        return GradientBoostingRegressor(**{"random_state": RANDOM_STATE, **params})
    if name == "xgboost":
        return XGBRegressor(**{"n_estimators": 400, "learning_rate": 0.05, "max_depth": 4,
                               "random_state": RANDOM_STATE, "n_jobs": -1, **params})
    if name == "lightgbm":
        return LGBMRegressor(**{"n_estimators": 400, "learning_rate": 0.05,
                                "random_state": RANDOM_STATE, "verbose": -1, **params})
    raise ValueError(f"Unknown model: {name}")


MODEL_NAMES = ["linear_regression", "ridge", "random_forest", "gradient_boosting", "xgboost", "lightgbm"]


def suggest_params(trial, name):
    """Optuna search space per model. Returns None for models with nothing to tune."""
    if name == "ridge":
        return {"alpha": trial.suggest_float("alpha", 1e-3, 100.0, log=True)}
    if name == "random_forest":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 600, step=100),
            "max_depth": trial.suggest_int("max_depth", 3, 20),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
            "max_features": trial.suggest_float("max_features", 0.3, 1.0),
        }
    if name == "gradient_boosting":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=100),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 6),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        }
    if name == "xgboost":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=100),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 8),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
    if name == "lightgbm":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000, step=100),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 4, 64),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "subsample_freq": 1,
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        }
    return None


def cv_score(name, engineered, params, X, y, cv):
    pipe = build_pipeline(make_regressor(name, params), engineered=engineered)
    res = cross_validate(pipe, X, y, cv=cv, scoring=("neg_root_mean_squared_error", "r2"))
    rmse = -res["test_neg_root_mean_squared_error"]
    return {
        "cv_rmse": float(rmse.mean()),
        "cv_rmse_std": float(rmse.std()),
        "cv_r2": float(res["test_r2"].mean()),
        "cv_r2_std": float(res["test_r2"].std()),
    }


class Tracker:
    """Thin MLflow wrapper so the script still runs with --no-mlflow."""

    def __init__(self, enabled):
        self.enabled = enabled
        if enabled:
            import mlflow
            self.mlflow = mlflow
            mlflow.set_tracking_uri(MLFLOW_URI)
            mlflow.set_experiment("exam-score")

    def log_run(self, run_name, params, metrics, nested=True):
        if not self.enabled:
            return
        with self.mlflow.start_run(run_name=run_name, nested=nested):
            self.mlflow.log_params(params)
            self.mlflow.log_metrics(metrics)

    def start_parent(self):
        if self.enabled:
            return self.mlflow.start_run(run_name=f"train-{datetime.now():%Y%m%d-%H%M%S}")
        return _NullContext()


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=30, help="Optuna trials per tuned model")
    parser.add_argument("--no-mlflow", action="store_true", help="Skip MLflow logging")
    args = parser.parse_args()

    df = pd.read_csv(DATA_PATH)
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    tracker = Tracker(enabled=not args.no_mlflow)

    with tracker.start_parent():
        # 1. Baseline CV for every model, with and without engineered features
        print(f"5-fold CV on {len(X_train)} training rows")
        print(f"{'model':<20}{'features':<12}{'CV RMSE':>16}{'CV R2':>16}")
        baseline = []
        for name in MODEL_NAMES:
            for engineered in (False, True):
                scores = cv_score(name, engineered, {}, X_train, y_train, cv)
                baseline.append({"model": name, "engineered": engineered, "params": {}, **scores})
                tracker.log_run(f"cv-{name}-{'fe' if engineered else 'base'}",
                                {"model": name, "engineered": engineered}, scores)
                print(f"{name:<20}{'engineered' if engineered else 'base':<12}"
                      f"{scores['cv_rmse']:>9.3f} +/-{scores['cv_rmse_std']:.3f}"
                      f"{scores['cv_r2']:>9.3f} +/-{scores['cv_r2_std']:.3f}")

        # Best feature set per model: engineered only if it clearly beats base
        best_per_model = {}
        for name in MODEL_NAMES:
            base = next(r for r in baseline if r["model"] == name and not r["engineered"])
            eng = next(r for r in baseline if r["model"] == name and r["engineered"])
            best_per_model[name] = eng if base["cv_rmse"] - eng["cv_rmse"] >= MIN_FEATURE_GAIN else base
        ranked = sorted(best_per_model.values(), key=lambda r: r["cv_rmse"])

        # 2. Tune the top K tunable models with Optuna (train set only)
        candidates = list(ranked)
        tunable = [r for r in ranked if r["model"] != "linear_regression"]
        for row in tunable[:TOP_K_TO_TUNE]:
            name, engineered = row["model"], row["engineered"]

            def objective(trial):
                params = suggest_params(trial, name)
                return cv_score(name, engineered, params, X_train, y_train, cv)["cv_rmse"]

            print(f"\nTuning {name} ({'engineered' if engineered else 'base'}) with {args.trials} Optuna trials")
            study = optuna.create_study(direction="minimize",
                                        sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
            study.optimize(objective, n_trials=args.trials)
            params = {**study.best_params}
            if name == "lightgbm":
                params["subsample_freq"] = 1
            scores = cv_score(name, engineered, params, X_train, y_train, cv)
            tuned = {"model": name, "engineered": engineered, "params": params, "tuned": True, **scores}
            candidates.append(tuned)
            tracker.log_run(f"tuned-{name}", {"model": name, "engineered": engineered, **params}, scores)
            print(f"  best CV RMSE {scores['cv_rmse']:.3f} (was {row['cv_rmse']:.3f})")

        # 3. Pick the winner by CV RMSE
        best = min(candidates, key=lambda r: r["cv_rmse"])
        label = f"{best['model']}{' (tuned)' if best.get('tuned') else ''}, " \
                f"{'engineered' if best['engineered'] else 'base'} features"
        print(f"\nSelected: {label}, CV RMSE {best['cv_rmse']:.3f}")

        # 4. Prediction interval from out-of-fold residuals on the train set
        oof_pred = cross_val_predict(
            build_pipeline(make_regressor(best["model"], best["params"]), engineered=best["engineered"]),
            X_train, y_train, cv=cv,
        )
        interval_half_width = float(np.quantile(np.abs(y_train - oof_pred), INTERVAL_LEVEL))

        # 5. One evaluation on the held-out test set
        eval_model = build_pipeline(make_regressor(best["model"], best["params"]), engineered=best["engineered"])
        eval_model.fit(X_train, y_train)
        raw_test_pred = eval_model.predict(X_test)
        test_pred = predict_scores(eval_model, X_test)
        test_metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_test, test_pred))),
            "r2": float(r2_score(y_test, test_pred)),
            "interval_coverage": float(np.mean(np.abs(y_test - test_pred) <= interval_half_width)),
            "clipped_predictions": int(np.sum((raw_test_pred < 0) | (raw_test_pred > 100))),
        }
        print(f"Held-out test RMSE: {test_metrics['rmse']:.3f}  R2: {test_metrics['r2']:.3f}")
        print(f"{INTERVAL_LEVEL:.0%} interval: +/-{interval_half_width:.2f}, "
              f"test coverage {test_metrics['interval_coverage']:.1%}")
        print(f"Clipped test predictions: {test_metrics['clipped_predictions']} of {len(X_test)}")

        # 6. Final model on all rows; it is not re-scored on the test set
        final_model = build_pipeline(make_regressor(best["model"], best["params"]), engineered=best["engineered"])
        final_model.fit(X, y)
        MODEL_DIR.mkdir(exist_ok=True)
        joblib.dump(final_model, MODEL_PATH)

        if tracker.enabled:
            tracker.mlflow.log_params({"selected_model": best["model"], "engineered": best["engineered"],
                                       **{f"param_{k}": v for k, v in best["params"].items()}})
            tracker.mlflow.log_metrics({"cv_rmse": best["cv_rmse"], "cv_r2": best["cv_r2"],
                                        "test_rmse": test_metrics["rmse"], "test_r2": test_metrics["r2"],
                                        "interval_half_width": interval_half_width,
                                        "interval_coverage": test_metrics["interval_coverage"]})
            tracker.mlflow.log_artifact(str(MODEL_PATH))

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "xgboost_version": xgboost.__version__,
        "lightgbm_version": lightgbm.__version__,
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
        "model": best["model"],
        "tuned": bool(best.get("tuned")),
        "engineered_features": best["engineered"],
        "params": best["params"],
        "features": FEATURES,
        "n_rows": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "cv": {"folds": CV_FOLDS, "rmse": best["cv_rmse"], "rmse_std": best["cv_rmse_std"],
               "r2": best["cv_r2"], "r2_std": best["cv_r2_std"]},
        "cv_leaderboard": sorted(
            [{k: r[k] for k in ("model", "engineered", "cv_rmse", "cv_r2")} | {"tuned": bool(r.get("tuned"))}
             for r in candidates],
            key=lambda r: r["cv_rmse"],
        ),
        "test_metrics": test_metrics,
        "interval": {"level": INTERVAL_LEVEL, "half_width": interval_half_width},
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Saved model to {MODEL_PATH.name} and metadata to {META_PATH.name}")


if __name__ == "__main__":
    main()

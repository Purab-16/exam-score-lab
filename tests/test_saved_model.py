import sklearn

from ml.pipeline import FEATURES, predict_scores


def test_model_predicts_whole_dataset(model, data):
    preds = predict_scores(model, data[FEATURES])
    assert len(preds) == len(data)
    assert ((preds >= 0) & (preds <= 100)).all()


def test_model_handles_unknown_parental_education(model, student):
    student["parental_education_level"] = "Unknown"
    assert 0 <= predict_scores(model, student)[0] <= 100


def test_meta_matches_installed_sklearn(meta):
    assert meta["sklearn_version"] == sklearn.__version__, "Re-run `python train.py`"


def test_meta_matches_feature_schema(meta):
    assert meta["features"] == FEATURES


def test_meta_has_honest_metrics(meta):
    assert meta["n_train"] + meta["n_test"] == meta["n_rows"]
    assert 0 < meta["test_metrics"]["rmse"] < 10
    assert 0.8 < meta["test_metrics"]["r2"] <= 1
    assert meta["interval"]["half_width"] > 0

"""The explainer behind the personal tips: exact formula for linear models, SHAP only when needed."""
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

import api.main as api_main
from api.main import create_app
from api.settings import Settings
from ml.insights import _is_linear, build_explainer, contributions_for
from ml.pipeline import FEATURES, TARGET, build_pipeline


@pytest.fixture(scope="module")
def linear_model(model):
    if not _is_linear(model.named_steps["regressor"]):
        pytest.skip("the saved model is not linear")
    return model


@pytest.fixture(scope="module")
def explainer(linear_model, data):
    return build_explainer(linear_model, data)


@pytest.fixture(scope="module")
def sample(data):
    return data[FEATURES].sample(100, random_state=3)


def test_linear_model_uses_the_formula(explainer):
    assert explainer["method"] == "linear"


def test_contributions_add_up_to_prediction_minus_average(linear_model, data, explainer, sample):
    average = linear_model.predict(data[FEATURES]).mean()
    for i in range(len(sample)):
        row = sample.iloc[[i]]
        total = sum(contributions_for(explainer, row).values())
        assert total == pytest.approx(float(linear_model.predict(row)[0]) - average, abs=1e-9)


def test_an_average_student_has_no_contributions(linear_model, data, explainer):
    """A student at every column's average gets about zero, for numeric columns."""
    row = data[FEATURES].iloc[[0]].copy()
    for col in ("study_hours_per_day", "sleep_hours"):
        row[col] = data[col].mean()
    contributions = contributions_for(explainer, row)
    assert abs(contributions["study_hours_per_day"]) < 1e-9
    assert abs(contributions["sleep_hours"]) < 1e-9


def test_formula_matches_shap_over_all_training_rows(linear_model, data, explainer, sample):
    shap = pytest.importorskip("shap")
    estimator, preprocessor = linear_model.named_steps["regressor"], linear_model[:-1]
    background = preprocessor.transform(data[FEATURES])
    matrix = preprocessor.transform(sample)
    reference = shap.LinearExplainer(estimator, shap.maskers.Independent(background, max_samples=len(background)))
    assert np.abs(explainer["explain"](matrix) - reference(matrix).values).max() < 1e-9


def test_shap_method_can_still_be_forced(linear_model, data, explainer, sample):
    pytest.importorskip("shap")
    forced = build_explainer(linear_model, data, method="shap")
    assert forced["method"] == "shap"
    row = sample.iloc[[0]]
    assert set(contributions_for(forced, row)) == set(contributions_for(explainer, row))


def test_unknown_method_is_rejected(linear_model, data):
    with pytest.raises(ValueError):
        build_explainer(linear_model, data, method="magic")


def test_tree_models_use_shap(data):
    pytest.importorskip("shap")
    model = build_pipeline(GradientBoostingRegressor(n_estimators=20, random_state=0)).fit(data[FEATURES], data[TARGET])
    tree_explainer = build_explainer(model, data)
    assert tree_explainer["method"] == "shap"
    contributions = contributions_for(tree_explainer, data[FEATURES].iloc[[0]])
    assert set(contributions) == set(FEATURES)


def test_tree_models_without_shap_fail_with_a_clear_message(monkeypatch, data):
    model = build_pipeline(RandomForestRegressor(n_estimators=5, random_state=0)).fit(data[FEATURES], data[TARGET])
    monkeypatch.setitem(sys.modules, "shap", None)  # makes `import shap` fail, as in the slim API image
    with pytest.raises(RuntimeError, match="shap"):
        build_explainer(model, data)


def test_the_api_works_without_the_shap_package(monkeypatch, linear_model, payload_weak):
    """The API image has no shap. Tips must still work."""
    monkeypatch.setitem(sys.modules, "shap", None)
    api_main.load_resources.cache_clear()
    try:
        with TestClient(create_app(Settings(rate_limit=False))) as client:
            res = client.post("/predict", json=payload_weak)
            assert res.status_code == 200
            tips = res.json()["tips"]
            assert tips and tips[0]["feature"] == "study_hours_per_day"
    finally:
        api_main.load_resources.cache_clear()


@pytest.fixture
def payload_weak(weak_student):
    return weak_student.iloc[0].to_dict()

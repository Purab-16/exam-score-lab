"""The API image installs requirements-api.txt; its pins must match the training environment."""
import re

from conftest import ROOT


def _pins(name):
    pins = {}
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)==([^\s#]+)", line)
        if m:
            pins[m.group(1).lower()] = m.group(2)
    return pins


def test_api_requirements_match_main_requirements():
    main, api = _pins("requirements.txt"), _pins("requirements-api.txt")
    assert api, "requirements-api.txt has no pinned packages"
    mismatched = {pkg: (ver, main.get(pkg)) for pkg, ver in api.items() if main.get(pkg) != ver}
    assert not mismatched, f"requirements-api.txt differs from requirements.txt: {mismatched}"


TREE_MODELS = {"random_forest", "gradient_boosting", "xgboost", "lightgbm"}


def test_api_requirements_cover_the_saved_model(meta):
    api = _pins("requirements-api.txt")
    needed = set()
    if meta["model"] in ("xgboost", "lightgbm"):
        needed.add(meta["model"])  # the model file needs its own library to load
    if meta["model"] in TREE_MODELS:
        needed.add("shap")  # tips for non-linear models are explained with SHAP
    missing = needed - set(api)
    assert not missing, f"Model is {meta['model']}; add {sorted(missing)} to requirements-api.txt"

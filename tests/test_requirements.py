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


def test_api_requirements_cover_the_saved_model(meta):
    api = _pins("requirements-api.txt")
    needed = {"xgboost": "xgboost", "lightgbm": "lightgbm"}.get(meta["model"])
    assert needed is None or needed in api, f"Model is {meta['model']}; add {needed} to requirements-api.txt"

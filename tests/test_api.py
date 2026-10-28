import pytest
from fastapi.testclient import TestClient

from api.main import app
from conftest import ROOT


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def payload(student):
    return student.iloc[0].to_dict()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_meta_describes_inputs(client):
    body = client.get("/meta").json()
    assert body["features"][0] == "age"
    assert body["numeric"]["study_hours_per_day"]["max"] == 8.3
    assert body["numeric"]["age"]["integer"] is True
    assert "Unknown" in body["categorical"]["parental_education_level"]["options"]
    assert body["model"]["sklearn_version_matches"] is True
    assert {h["feature"] for h in body["habits"]} >= {"study_hours_per_day", "diet_quality"}


def test_predict(client, payload):
    body = client.post("/predict", json=payload).json()
    assert 0 <= body["score"] <= 100
    assert body["interval"]["low"] <= body["score"] <= body["interval"]["high"]
    assert isinstance(body["tips"], list)


def test_predict_weak_student_gets_tips(client, weak_student):
    body = client.post("/predict", json=weak_student.iloc[0].to_dict()).json()
    assert body["tips"]
    assert body["tips"][0]["feature"] == "study_hours_per_day"
    assert all(t["gain"] > 0 for t in body["tips"])


def test_predict_flags_edge_inputs(client, payload):
    payload["study_hours_per_day"] = 8.3
    assert "study_hours_per_day" in client.post("/predict", json=payload).json()["edge_features"]


@pytest.mark.parametrize("field,value", [("gender", "Robot"), ("diet_quality", "Excellent"),
                                         ("age", 5), ("study_hours_per_day", -1)])
def test_predict_rejects_bad_input(client, payload, field, value):
    payload[field] = value
    assert client.post("/predict", json=payload).status_code == 422


def test_what_if(client, payload):
    res = client.post("/what-if", json={"student": payload, "changes": {"study_hours_per_day": 6}})
    body = res.json()
    assert res.status_code == 200
    assert body["new_score"] > body["base_score"]
    assert body["delta"] == pytest.approx(body["new_score"] - body["base_score"], abs=0.02)


def test_what_if_no_changes(client, payload):
    body = client.post("/what-if", json={"student": payload, "changes": {}}).json()
    assert body["delta"] == 0


@pytest.mark.parametrize("changes", [{"height": 180}, {"age": 5}, {"diet_quality": "Excellent"}])
def test_what_if_rejects_bad_changes(client, payload, changes):
    assert client.post("/what-if", json={"student": payload, "changes": changes}).status_code == 422


def test_batch_with_template(client):
    template = client.get("/template.csv")
    assert template.status_code == 200
    res = client.post("/predict/batch", files={"file": ("t.csv", template.content, "text/csv")})
    body = res.json()
    assert res.status_code == 200
    assert body["summary"]["count"] == 5
    assert {"student_id", "predicted_score", "range_low", "range_high"} <= set(body["columns"])


def test_batch_keeps_empty_cells_as_null(client, data):
    df = data.drop(columns=["exam_score"]).head(5)
    df.loc[0, "gender"] = None
    res = client.post("/predict/batch", files={"file": ("s.csv", df.to_csv(index=False), "text/csv")})
    assert res.status_code == 200
    assert res.json()["rows"][0]["gender"] is None


def test_batch_reports_errors(client, data):
    df = data.drop(columns=["exam_score"]).head(5).astype(object)
    df.loc[1, "diet_quality"] = "Excellent"
    res = client.post("/predict/batch", files={"file": ("s.csv", df.to_csv(index=False), "text/csv")})
    assert res.status_code == 422
    assert any("Excellent" in e for e in res.json()["detail"])


def test_batch_rejects_non_csv(client):
    res = client.post("/predict/batch", files={"file": ("x.csv", b"\x00\x01\x02", "text/csv")})
    assert res.status_code == 422


def test_insights(client):
    body = client.get("/insights").json()
    assert body["count"] == 1000
    assert sum(b["count"] for b in body["histogram"]) == 1000
    assert body["correlations"][0]["feature"] == "study_hours_per_day"
    assert len(body["predicted_vs_actual"]) == 1000

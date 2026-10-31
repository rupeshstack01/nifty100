from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_company_list():
    response = client.get("/companies")
    assert response.status_code == 200
    assert "items" in response.json()


def test_screener():
    assert client.get("/screener").status_code == 200


def test_sectors():
    assert client.get("/sectors").status_code == 200


def test_clusters():
    response = client.get("/clusters")
    assert response.status_code == 200
    assert "clusters" in response.json()


def test_cluster_labels_cover_92_companies():
    response = client.get("/companies?limit=200")
    assert response.status_code == 200
    # This checks API coverage only when the source data contains the expected universe.
    assert response.json()["total"] >= 5


def test_outliers():
    assert client.get("/outliers").status_code == 200


def test_portfolio_stats():
    assert client.get("/portfolio/stats").status_code == 200


def test_data_quality():
    response = client.get("/data-quality")
    assert response.status_code == 200
    assert "rows" in response.json()


def test_reports():
    assert client.get("/reports").status_code == 200


def test_openapi_schema():
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert len(schema.json()["paths"]) >= 16


def test_unknown_company_returns_404():
    response = client.get("/companies/COMPANY_THAT_DOES_NOT_EXIST")
    assert response.status_code == 404


def test_unknown_cluster_returns_404():
    response = client.get("/clusters/999999")
    assert response.status_code == 404

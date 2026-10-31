import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.api.main as api


SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Healthcare",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
]


@pytest.fixture
def client(monkeypatch):
    sector_data = pd.DataFrame({
        "company_id": ["COMPANY_A", "COMPANY_B"],
        "broad_sector": ["Industrials", "Energy"],
        "sub_sector": ["Capital Goods", "Power"],
    })

    company_data = pd.DataFrame({
        "company_id": ["COMPANY_A", "COMPANY_B"],
        "year": [2024, 2024],
    })

    monkeypatch.setattr(api, "sector_data", lambda: sector_data)
    monkeypatch.setattr(api, "joined_latest", lambda: company_data)

    with TestClient(api.app) as test_client:
        yield test_client


@pytest.mark.parametrize("sector", SECTORS)
def test_sector_detail_returns_valid_sector(client, sector):
    # Route must return a valid response for sectors present in the data.
    if sector not in {"Industrials", "Energy"}:
        response = client.get("/sectors/" + sector.replace(" ", "%20"))
        assert response.status_code == 404
        return

    response = client.get("/sectors/" + sector.replace(" ", "%20"))
    assert response.status_code == 200

    data = response.json()
    assert data["sector"] == sector
    assert data["count"] > 0
    assert len(data["companies"]) == data["count"]


def test_unknown_sector_returns_404(client):
    response = client.get("/sectors/NotARealSector")
    assert response.status_code == 404


def test_sector_data_unavailable_returns_404(client, monkeypatch):
    monkeypatch.setattr(api, "sector_data", lambda: pd.DataFrame())
    response = client.get("/sectors/Industrials")
    assert response.status_code == 404

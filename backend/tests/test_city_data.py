"""City Hall client: polite caching, honest fallbacks, and the slim API surface."""
import json
import os
import time

os.environ.setdefault("TMBG_OFFLINE", "1")

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import pmt_client


def test_health_and_no_legacy_endpoints():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        for path in ("/api/hotspots", "/api/network", "/api/sesizari/summary?lat=45.74&lng=21.23"):
            assert c.get(path).status_code == 404, path


def test_decode_polyline():
    # canonical example from the Google polyline spec
    assert pmt_client.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]


@pytest.fixture
def fresh_client(tmp_path, monkeypatch):
    """Empty cache folder, nothing remembered, live calls allowed but failing."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "OFFLINE", False)
    monkeypatch.setattr(pmt_client, "_mem", {})
    monkeypatch.setattr(pmt_client, "_status", {})

    def no_network(url, params=None):
        raise ConnectionError("no internet")
    monkeypatch.setattr(pmt_client, "http_get_json", no_network)
    return tmp_path


def test_without_internet_and_without_a_saved_copy_nothing_is_invented(fresh_client):
    data, prov = pmt_client.get_parking()
    assert prov.source == "unavailable" and not pmt_client.available(prov)
    assert data == {"features": [], "tariffs": {}}
    lines, prov = pmt_client.get_wallet_types()
    assert lines == [] and prov.source == "unavailable"


def test_without_internet_an_old_saved_copy_is_used(fresh_client):
    payload = {"features": [{"kind": "street", "tariff": "yellow", "coordinates": []}], "tariffs": {}}
    two_days_ago = time.time() - 2 * 24 * 3600          # older than the 24 h TTL
    (fresh_client / f"parking.v{pmt_client.CACHE_SCHEMA_VERSION}.json").write_text(
        json.dumps({"fetchedAt": two_days_ago, "payload": payload}), encoding="utf-8")
    data, prov = pmt_client.get_parking()
    assert data == payload
    assert prov.source == "cache (stale)" and pmt_client.available(prov)

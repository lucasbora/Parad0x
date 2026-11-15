"""City Hall client helpers and the slimmed API surface."""
import os

os.environ.setdefault("TMBG_OFFLINE", "1")

from fastapi.testclient import TestClient

from app.main import app
from app.services.pmt_client import decode_polyline, sanitize_sesizari


def test_health_and_no_legacy_endpoints():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        for path in ("/api/hotspots", "/api/network", "/api/sesizari/summary?lat=45.74&lng=21.23"):
            assert c.get(path).status_code == 404, path


def test_sesizari_gdpr_sanitizer_strips_personal_data():
    raw = [{"categorie": "Străzi și trotuare", "status": "In lucru", "descriere": "Ion Popescu ...",
            "nume": "Ion Popescu", "poze": ["https://x/y.jpg"], "email": "a@b.ro"},
           {"categorie": "Transport public", "status": "Finalizata", "telefon": "07..."}]
    out = sanitize_sesizari(raw)
    flat = repr(out)
    assert "Popescu" not in flat and "jpg" not in flat and "@" not in flat
    assert out["total"] == 2


def test_decode_polyline():
    # canonical example from the Google polyline spec
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]]

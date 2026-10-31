from fastapi.testclient import TestClient

from mana.web.app import app


def test_saude():
    r = TestClient(app).get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

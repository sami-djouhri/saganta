"""Loeschen einer Aufgabe raeumt ihre Verknuepfungen in den Notizen ab (seit 2026-11-21)."""

import httpx
from jose import jwt

from app import notizen
from app.config import settings


def _neu(client, kopf):
    return client.post("/api/aufgaben", json={"titel": "Weg damit"}, headers=kopf).json()


def test_loeschen_ruft_die_notizen_im_namen_des_aufrufers(client, kopf, monkeypatch):
    gesehen = []

    def handler(anfrage: httpx.Request) -> httpx.Response:
        gesehen.append(anfrage)
        return httpx.Response(200, json={"entfernt": 1})

    echter_client = httpx.Client
    monkeypatch.setattr(settings, "notizen_api_url", "http://notizen.test")
    monkeypatch.setattr(
        notizen.httpx, "Client", lambda **kw: echter_client(transport=httpx.MockTransport(handler), **kw)
    )
    a = _neu(client, kopf)
    assert client.delete(f"/api/aufgaben/{a['id']}", headers=kopf).status_code == 204

    assert len(gesehen) == 1
    anfrage = gesehen[0]
    assert anfrage.method == "DELETE"
    assert anfrage.url.path == "/api/notizen/verknuepft"
    assert dict(anfrage.url.params) == {"typ": "aufgabe", "ref": a["id"]}
    token = anfrage.headers["Authorization"].removeprefix("Bearer ")
    inhalt = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience="notizen-api")
    assert inhalt["sub"] == "nutzer-eins"
    assert inhalt["exp"] - inhalt["iat"] == 60


def test_notizen_aus_hindert_das_loeschen_nicht(client, kopf, monkeypatch):
    def handler(anfrage: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("weg")

    echter_client = httpx.Client
    monkeypatch.setattr(settings, "notizen_api_url", "http://notizen.test")
    monkeypatch.setattr(
        notizen.httpx, "Client", lambda **kw: echter_client(transport=httpx.MockTransport(handler), **kw)
    )
    a = _neu(client, kopf)
    assert client.delete(f"/api/aufgaben/{a['id']}", headers=kopf).status_code == 204
    assert client.get(f"/api/aufgaben/{a['id']}", headers=kopf).status_code == 404


def test_fremde_aufgabe_loest_keinen_aufruf_aus(client, kopf, kopf_zwei, monkeypatch):
    gesehen = []
    monkeypatch.setattr(settings, "notizen_api_url", "http://notizen.test")
    monkeypatch.setattr(notizen, "_abraeumen", lambda me, ref: gesehen.append(ref))
    a = _neu(client, kopf)
    assert client.delete(f"/api/aufgaben/{a['id']}", headers=kopf_zwei).status_code == 404
    assert gesehen == []

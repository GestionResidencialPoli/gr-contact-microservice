import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import JWT_SECRET, SessionLocal, app


@pytest.fixture(autouse=True)
def clean_database():
    assert "_test_db" in os.environ["DATABASE_URL"]
    with SessionLocal() as db:
        db.execute(text("TRUNCATE contact_status_history, contact_requests RESTART IDENTITY CASCADE"))
        db.commit()


def token(roles: list[str]) -> str:
    return jwt.encode(
        {"uid": 1, "roles": roles, "exp": datetime.now(UTC) + timedelta(hours=1)},
        JWT_SECRET,
        algorithm="HS256",
    )


def create_payload() -> dict:
    return {
        "nombre": "Daniela García",
        "email": "daniela@example.com",
        "telefono": None,
        "mensaje": "Quiero conocer más sobre el proyecto residencial.",
        "consentimiento": True,
        "consentimiento_version": "contacto-v1",
    }


def test_public_submission_is_persisted_with_consent_history():
    client = TestClient(app)
    response = client.post("/api/v1/contacto/solicitudes", json=create_payload())
    assert response.status_code == 201
    assert response.json()["status"] == "NUEVA"
    with SessionLocal() as db:
        assert db.scalar(text("SELECT count(*) FROM contact_requests")) == 1
        assert db.scalar(text("SELECT count(*) FROM contact_status_history")) == 1


def test_validation_and_consent_are_required():
    client = TestClient(app)
    payload = create_payload()
    payload["consentimiento"] = False
    response = client.post("/api/v1/contacto/solicitudes", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONSENTIMIENTO_REQUERIDO"
    payload["email"] = "no-es-correo"
    response = client.post("/api/v1/contacto/solicitudes", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SOLICITUD_INVALIDA"


def test_admin_inbox_requires_role_and_csrf_for_status_change():
    client = TestClient(app)
    client.post("/api/v1/contacto/solicitudes", json=create_payload())
    path = "/api/v1/contacto/solicitudes"
    assert client.get(path).status_code == 401
    assert client.get(path, cookies={"access_token": token(["RESIDENTE"])}).status_code == 403
    cookies = {"access_token": token(["ADMINISTRACION"]), "XSRF-TOKEN": "test-csrf"}
    response = client.get(path, cookies=cookies)
    assert response.status_code == 200
    assert len(response.json()) == 1
    change_path = f"{path}/1/estado"
    assert client.patch(change_path, json={"status": "EN_REVISION"}, cookies=cookies).status_code == 403
    response = client.patch(
        change_path, json={"status": "EN_REVISION"}, cookies=cookies, headers={"X-XSRF-TOKEN": "test-csrf"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "EN_REVISION"
    with SessionLocal() as db:
        assert db.scalar(text("SELECT count(*) FROM contact_status_history")) == 2

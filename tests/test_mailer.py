import smtplib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app import mailer
from app.main import app


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host, port, **_):
        self.host = host
        self.port = port
        self.logins = []
        self.messages = []
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, user, password):
        self.logins.append((user, password))

    def send_message(self, message):
        self.messages.append(message)


@pytest.fixture
def smtp(monkeypatch):
    FakeSmtp.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSmtp)
    monkeypatch.setenv("SMTP_USER", "remitente@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("CONTACT_NOTIFY_TO", "destino@example.com")
    return FakeSmtp


def payload(**overrides) -> dict:
    return {
        "nombre": "Daniela García",
        "email": "daniela@example.com",
        "telefono": "3126222069",
        "mensaje": "Quiero conocer más sobre el proyecto residencial.\nGracias.",
        "consentimiento": True,
        "consentimiento_version": "contacto-v1",
    } | overrides


def notification(**overrides) -> mailer.ContactNotification:
    values = {
        "id": 7,
        "nombre": "Daniela García",
        "email": "daniela@example.com",
        "telefono": None,
        "mensaje": "Hola",
        "created_at": datetime(2026, 9, 29, 20, 30, tzinfo=UTC),
    } | overrides
    return mailer.ContactNotification(**values)


def test_submission_sends_styled_email_to_configured_recipient(smtp):
    response = TestClient(app).post("/api/v1/contacto/solicitudes", json=payload())

    assert response.status_code == 201
    [client] = smtp.instances
    assert (client.host, client.port) == ("smtp.gmail.com", 465)
    assert client.logins == [("remitente@example.com", "abcdefghijklmnop")]
    [message] = client.messages
    assert message["To"] == "destino@example.com"
    assert "daniela@example.com" in message["Reply-To"]
    assert f"#{response.json()['id']}" in message["Subject"]
    html = message.get_body(("html",)).get_content()
    assert "Daniela García" in html
    assert "proyecto residencial.<br>Gracias." in html
    assert "3126222069" in html
    assert "Quiero conocer" in message.get_body(("plain",)).get_content()


def test_submission_without_smtp_configuration_skips_email(monkeypatch):
    for name in ("SMTP_USER", "SMTP_PASSWORD", "CONTACT_NOTIFY_TO"):
        monkeypatch.delenv(name, raising=False)
    FakeSmtp.instances = []
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSmtp)

    response = TestClient(app).post("/api/v1/contacto/solicitudes", json=payload())

    assert response.status_code == 201
    assert FakeSmtp.instances == []


def test_smtp_failure_keeps_the_request_saved(smtp, monkeypatch):
    def fail(*_):
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(FakeSmtp, "login", fail)

    response = TestClient(app).post("/api/v1/contacto/solicitudes", json=payload())

    assert response.status_code == 201
    assert response.json()["status"] == "NUEVA"


def test_html_escapes_user_content():
    html = mailer.render_html(notification(nombre="<b>Eva</b>", mensaje="<script>alert(1)</script>"))

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;Eva&lt;/b&gt;" in html


def test_date_is_shown_in_colombian_time():
    assert "29/09/2026 · 03:30 PM" in mailer.render_html(notification())

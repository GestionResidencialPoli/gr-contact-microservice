# gr-contact-microservice

API FastAPI para solicitudes públicas de contacto y su gestión por administración. PostgreSQL es el dueño del esquema mediante Alembic.

## Rutas

- `GET /health`, `GET /health/ready`.
- `POST /api/v1/contacto/solicitudes` es público; requiere consentimiento explícito y guarda su versión, fecha y el historial de estado.
- `GET /api/v1/contacto/solicitudes[?status=...]`, `GET /api/v1/contacto/solicitudes/{id}` y `PATCH /api/v1/contacto/solicitudes/{id}/estado` requieren cookie `access_token` con rol `ADMINISTRACION`; las escrituras requieren `X-XSRF-TOKEN` igual a la cookie `XSRF-TOKEN`.

La aplicación se ejecuta en el puerto 4500. Configura `DATABASE_URL`, el mismo `JWT_SECRET` de Identidad y `CORS_ALLOWED_ORIGINS` según `.env.example`. No se almacena la IP del visitante.

Para pruebas instala `requirements-dev.txt`, usa una base cuyo nombre contenga `_test_db` y ejecuta `alembic upgrade head` y `python -m pytest -q tests`.

Servicio FastAPI para solicitudes de contacto públicas y su bandeja administrativa. La base `gr_contact_db` es propiedad exclusiva del servicio y evoluciona únicamente mediante Alembic.

## Desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://gr_user:gr_password@localhost:5432/gr_contact_db"
alembic upgrade head
uvicorn app.main:app --port 4500
```

La única ruta pública de negocio es `POST /api/v1/contacto/solicitudes`. La consulta y el cambio de estado requieren el rol `ADMINISTRACION` en la cookie JWT. El consentimiento se guarda con versión y fecha; la IP no se almacena.

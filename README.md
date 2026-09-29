# gr-contact-microservice

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

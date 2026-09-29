# gr-contact-microservice

- FastAPI, SQLAlchemy y Alembic; Alembic es el único dueño del esquema.
- Las rutas públicas y permisos deben tener pruebas de método, ruta y rol.
- Las ramas salen de `develop` con `feature/GR-###-descripcion`; los commits usan `tipo(scope): GR-### descripcion breve`.
- No guardar IP cruda ni secretos. Documentar variables en `.env.example`.

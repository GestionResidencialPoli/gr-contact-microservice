from datetime import UTC, datetime
from enum import Enum
import os
from typing import Generator

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://gr_user:gr_password@localhost:5432/gr_contact_db")
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret-change-me")

class Base(DeclarativeBase):
    pass

class ContactStatus(str, Enum):
    NUEVA = "NUEVA"
    EN_REVISION = "EN_REVISION"
    RESPONDIDA = "RESPONDIDA"
    CERRADA = "CERRADA"

class ContactRequest(Base):
    __tablename__ = "contact_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320))
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mensaje: Mapped[str] = mapped_column(Text)
    consentimiento_version: Mapped[str] = mapped_column(String(40))
    consentimiento_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[ContactStatus] = mapped_column(SqlEnum(ContactStatus, name="contact_status"), default=ContactStatus.NUEVA)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    history: Mapped[list["ContactStatusHistory"]] = relationship(back_populates="request", cascade="all, delete-orphan")

class ContactStatusHistory(Base):
    __tablename__ = "contact_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("contact_requests.id", ondelete="CASCADE"))
    from_status: Mapped[ContactStatus | None] = mapped_column(SqlEnum(ContactStatus, name="contact_status", create_type=False), nullable=True)
    to_status: Mapped[ContactStatus] = mapped_column(SqlEnum(ContactStatus, name="contact_status", create_type=False))
    changed_by_user_id: Mapped[int | None] = mapped_column(nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    request: Mapped[ContactRequest] = relationship(back_populates="history")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db

class ContactCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefono: str | None = Field(default=None, max_length=30)
    mensaje: str = Field(min_length=10, max_length=4000)
    consentimiento: bool
    consentimiento_version: str = Field(min_length=1, max_length=40)

    @field_validator("nombre", "mensaje", "consentimiento_version")
    @classmethod
    def trim_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El valor no puede estar vacío")
        return value

class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr
    telefono: str | None
    mensaje: str
    status: ContactStatus
    consentimiento_version: str
    consentimiento_at: datetime
    created_at: datetime
    updated_at: datetime

class StatusChange(BaseModel):
    status: ContactStatus

def current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail={"code": "NO_AUTENTICADO", "message": "Sesión requerida"})
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "NO_AUTENTICADO", "message": "Sesión inválida"}) from exc
    if "ADMINISTRACION" not in claims.get("roles", []):
        raise HTTPException(status_code=403, detail={"code": "SIN_PERMISOS", "message": "Se requiere administración"})
    return claims

app = FastAPI(title="GR Contact Microservice", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3006,http://localhost:3001").split(","), allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "X-XSRF-TOKEN", "X-Correlation-Id"])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ready"}

@app.post("/api/v1/contacto/solicitudes", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)) -> ContactRequest:
    if not payload.consentimiento:
        raise HTTPException(status_code=422, detail={"code": "CONSENTIMIENTO_REQUERIDO", "message": "Debes aceptar el consentimiento para enviar el mensaje"})
    item = ContactRequest(nombre=payload.nombre, email=str(payload.email).lower(), telefono=payload.telefono.strip() if payload.telefono else None, mensaje=payload.mensaje, consentimiento_version=payload.consentimiento_version, consentimiento_at=datetime.now(UTC), status=ContactStatus.NUEVA)
    db.add(item)
    db.flush()
    db.add(ContactStatusHistory(request_id=item.id, from_status=None, to_status=ContactStatus.NUEVA))
    db.commit()
    db.refresh(item)
    return item

@app.get("/api/v1/contacto/solicitudes", response_model=list[ContactResponse])
def list_contacts(status_filter: ContactStatus | None = Query(default=None, alias="status"), _: dict = Depends(current_user), db: Session = Depends(get_db)) -> list[ContactRequest]:
    query = select(ContactRequest).order_by(ContactRequest.created_at.desc())
    if status_filter:
        query = query.where(ContactRequest.status == status_filter)
    return list(db.scalars(query).all())

@app.get("/api/v1/contacto/solicitudes/{request_id}", response_model=ContactResponse)
def get_contact(request_id: int, _: dict = Depends(current_user), db: Session = Depends(get_db)) -> ContactRequest:
    item = db.get(ContactRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "SOLICITUD_NO_ENCONTRADA", "message": "Solicitud no encontrada"})
    return item

@app.patch("/api/v1/contacto/solicitudes/{request_id}/estado", response_model=ContactResponse)
def change_status(request_id: int, payload: StatusChange, user: dict = Depends(current_user), db: Session = Depends(get_db)) -> ContactRequest:
    item = db.get(ContactRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "SOLICITUD_NO_ENCONTRADA", "message": "Solicitud no encontrada"})
    previous = item.status
    item.status = payload.status
    item.updated_at = datetime.now(UTC)
    db.add(ContactStatusHistory(request_id=item.id, from_status=previous, to_status=payload.status, changed_by_user_id=user.get("uid")))
    db.commit()
    db.refresh(item)
    return item

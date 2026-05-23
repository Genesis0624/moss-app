"""
MOSS - Modelo Premio (v3 — Economía / Lista de Deseos)
Renombra costo_estimado → costo_financiero
y añade la relación con Objetivo (micro-premios).

Flujo de desbloqueo:
  Objetivo.completar() → premio_parcial.desbloquear()  (micro-recompensa)
  Meta.check_completar() → premio.desbloquear()        (recompensa final)
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from backend.app import db


class PremioEstado(PyEnum):
    BLOQUEADO    = "Bloqueado"
    DESBLOQUEADO = "Desbloqueado"
    OBTENIDO     = "Obtenido"


class Premio(db.Model):
    __tablename__ = "premios"

    id    = db.Column(db.String(36), primary_key=True,
                      default=lambda: str(uuid.uuid4()))
    titulo = db.Column(db.String(300), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    costo_financiero = db.Column(db.Float, nullable=True)
    imagen_url = db.Column(db.String(500), nullable=True)

    estado           = db.Column(db.Enum(PremioEstado),
                                 default=PremioEstado.BLOQUEADO, nullable=False)
    fecha_desbloqueo = db.Column(db.DateTime, nullable=True)
    fecha_obtenido   = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relaciones ORM ─────────────────────────────────────────────────────────
    metas = db.relationship("Meta", back_populates="premio",
                            lazy="dynamic", cascade="all, delete-orphan")
    objetivos_parciales = db.relationship("Objetivo", back_populates="premio_parcial",
                                          lazy="dynamic", cascade="all, delete-orphan")

    # ── Métodos ────────────────────────────────────────────────────────────────
    def desbloquear(self):
        if self.estado == PremioEstado.BLOQUEADO:
            self.estado           = PremioEstado.DESBLOQUEADO
            self.fecha_desbloqueo = datetime.utcnow()
            db.session.flush()

    def marcar_obtenido(self):
        self.estado         = PremioEstado.OBTENIDO
        self.fecha_obtenido = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            "id":               self.id,
            "titulo":           self.titulo,
            "descripcion":      self.descripcion,
            "costo_financiero": self.costo_financiero,
            "imagen_url":       self.imagen_url,
            "estado":           self.estado.value,
            "fecha_desbloqueo": self.fecha_desbloqueo.isoformat() if self.fecha_desbloqueo else None,
            "fecha_obtenido":   self.fecha_obtenido.isoformat()   if self.fecha_obtenido   else None,
        }

    def __repr__(self):
        return f"<Premio '{self.titulo}' | {self.estado.value}>"

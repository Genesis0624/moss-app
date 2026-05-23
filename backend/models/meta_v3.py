"""
MOSS - Modelo Meta (v3 — Sistema RPG + Motor de Recomendación)
Versión definitiva que integra todo el sistema de pilares,
gamificación y el algoritmo de recomendación.
"""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.models.pilar import Pilar
    from backend.models.premio_v3 import Premio
    from backend.models.objetivo_v3 import Objetivo
    from backend.models.task import Task

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from backend.app import db


class MetaEstado(PyEnum):
    ACTIVA = "Activa"
    EN_PAUSA = "En Pausa"
    COMPLETADA = "Completada"


class MetaPlazo(PyEnum):
    CORTO = "Corto"
    MEDIANO = "Mediano"
    LARGO = "Largo"


class Meta(db.Model):
    __tablename__ = "metas"

    # Identidad
    id = db.Column(db.String(36), primary_key=True,
                   default=lambda: str(uuid.uuid4()))
    titulo = db.Column(db.String(500), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)

    # Visual
    icono = db.Column(db.String(100), nullable=True)
    foto_portada_url = db.Column(db.String(500), nullable=True)

    # Clasificación
    plazo = db.Column(db.Enum(MetaPlazo), default=MetaPlazo.MEDIANO)
    estado = db.Column(db.Enum(MetaEstado), default=MetaEstado.ACTIVA)

    # Motor de Recomendación
    prioridad_impacto = db.Column(db.Integer, default=3)

    # Relaciones FK
    pilar_id = db.Column(db.String(36), db.ForeignKey("pilares.id"),
                         nullable=False)
    premio_id = db.Column(db.String(36), db.ForeignKey("premios.id"),
                          nullable=True)

    # Timestamps
    fecha_inicio = db.Column(db.Date, nullable=True)
    fecha_limite = db.Column(db.Date, nullable=True)
    fecha_completada = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones ORM (back_populates emparejadas en los otros modelos)
    pilar = db.relationship(
        "Pilar",
        back_populates="metas",
        foreign_keys=[pilar_id]
    )

    premio = db.relationship(
        "Premio",
        back_populates="metas",
        foreign_keys=[premio_id]
    )

    objetivos = db.relationship(
        "Objetivo",
        back_populates="meta",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="Objetivo.meta_id"
    )

    tareas = db.relationship(
        "Task",
        back_populates="meta",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="Task.meta_id"
    )

    # Propiedades calculadas
    @property
    def progreso_calculado(self):
        total = self.objetivos.count()
        if total == 0:
            return 0.0
        completados = self.objetivos.filter_by(estado="Completado").count()
        return round((completados / total) * 100, 1)

    @property
    def objetivos_completados(self):
        return self.objetivos.filter_by(estado="Completado").count()

    @property
    def objetivos_total(self):
        return self.objetivos.count()

    @property
    def score_recomendacion(self):
        if not self.pilar:
            return 0
        ultima_ev = self.pilar.ultima_evaluacion
        puntuacion_pilar = ultima_ev.puntuacion if ultima_ev else 5
        gap = 10 - puntuacion_pilar
        score = gap * (self.prioridad_impacto or 1)
        return score

    @property
    def etiqueta_recomendacion(self):
        score = self.score_recomendacion
        if score >= 30:
            return "🚨 Prioridad de Balance"
        if score >= 20:
            return "⚡ Alta Relevancia"
        if score >= 10:
            return "💡 Recomendada"
        return None

    # Gamificación
    def check_completar_y_otorgar_xp(self):
        if self.progreso_calculado < 100:
            return False
        self.estado = MetaEstado.COMPLETADA
        self.fecha_completada = datetime.utcnow()
        if self.premio_id and self.premio:
            self.premio.desbloquear()
        if self.pilar:
            self.pilar.otorgar_xp(200, fuente=f"meta_completada:{self.id}")
        db.session.commit()
        return True

    # Serialización
    def to_dict(self, include_objetivos=False, include_score=False):
        data = {
            "id": self.id,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "icono": self.icono,
            "foto_portada_url": self.foto_portada_url,
            "plazo": self.plazo.value if self.plazo else None,
            "estado": self.estado.value if self.estado else None,
            "prioridad_impacto": self.prioridad_impacto,
            "pilar_id": self.pilar_id,
            "pilar_nombre": self.pilar.nombre if self.pilar else None,
            "pilar_nivel": self.pilar.nivel_actual if self.pilar else None,
            "premio_id": self.premio_id,
            "premio": self.premio.to_dict() if self.premio else None,
            "progreso_calculado": self.progreso_calculado,
            "objetivos_completados": self.objetivos_completados,
            "objetivos_total": self.objetivos_total,
            "fecha_inicio": self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            "fecha_limite": self.fecha_limite.isoformat() if self.fecha_limite else None,
            "fecha_completada": self.fecha_completada.isoformat() if self.fecha_completada else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_score:
            data["score_recomendacion"] = self.score_recomendacion
            data["etiqueta_recomendacion"] = self.etiqueta_recomendacion
        if include_objetivos:
            data["objetivos"] = [o.to_dict() for o in self.objetivos.all()]
        return data

    def __repr__(self):
        return f"<Meta '{self.titulo}' | {self.estado.value} | {self.progreso_calculado}%>"

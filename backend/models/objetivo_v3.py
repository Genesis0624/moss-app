"""
MOSS - Modelo Objetivo (v3 — Sistema RPG)
Los bloques de avance de una Meta. Duración: 1 a 4 semanas.
La fecha límite NO se pone aquí — se asigna en la Planificación Semanal.

Sistema de XP:
  Al completar un objetivo → +50 XP al Pilar de la meta padre.
  Este XP se otorga vía meta.pilar.otorgar_xp()

Conexiones:
  Objetivo ──► Meta            (N:1)
  Objetivo ──► Premio          (N:1 — micro-recompensa opcional)
  Objetivo ◄── Task[]          (futuro: Task.objetivo_id)
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from backend.app import db


class ObjetivoEstado(PyEnum):
    PENDIENTE    = "Pendiente"
    EN_PROGRESO  = "En Progreso"
    COMPLETADO   = "Completado"
    CANCELADO    = "Cancelado"


class Objetivo(db.Model):
    __tablename__ = "objetivos"

    # ── Identidad ──────────────────────────────────────────────────────────────
    id     = db.Column(db.String(36), primary_key=True,
                       default=lambda: str(uuid.uuid4()))
    titulo = db.Column(db.String(500), nullable=False)

    # ── Contenido / Planificación ──────────────────────────────────────────────
    recursos   = db.Column(db.Text, nullable=True)
    obstaculos = db.Column(db.Text, nullable=True)
    soluciones = db.Column(db.Text, nullable=True)

    # ── Estado ─────────────────────────────────────────────────────────────────
    estado = db.Column(db.Enum(ObjetivoEstado),
                       default=ObjetivoEstado.PENDIENTE, nullable=False)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    fecha_completado = db.Column(db.DateTime, nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relaciones FK ──────────────────────────────────────────────────────────
    meta_id = db.Column(db.String(36), db.ForeignKey("metas.id"),
                        nullable=False)

    premio_parcial_id = db.Column(db.String(36), db.ForeignKey("premios.id"),
                                  nullable=True)

    # ── Relaciones ORM ─────────────────────────────────────────────────────────
    meta = db.relationship("Meta", back_populates="objetivos")
    premio_parcial = db.relationship("Premio", back_populates="objetivos_parciales")

    # ── Relación futura con Tareas ─────────────────────────────────────────────
    # tareas = db.relationship("Task", back_populates="objetivo", lazy="dynamic")

    # ── Lógica de completado ───────────────────────────────────────────────────
    def completar(self):
        if self.estado == ObjetivoEstado.COMPLETADO:
            return {"ya_completado": True}

        self.estado           = ObjetivoEstado.COMPLETADO
        self.fecha_completado = datetime.utcnow()
        db.session.flush()

        efectos = {
            "objetivo_id":     self.id,
            "xp_ganado":       0,
            "nivel_subio":     False,
            "meta_progreso":   0,
            "meta_completada": False,
            "premio_parcial":  None,
            "premio_final":    None,
        }

        # XP al Pilar
        if self.meta and self.meta.pilar:
            xp_result = self.meta.pilar.otorgar_xp(
                50, fuente=f"objetivo_completado:{self.id}"
            )
            efectos["xp_ganado"]   = xp_result["xp_ganado"]
            efectos["nivel_subio"] = xp_result["subio_nivel"]
            efectos["nivel_nuevo"] = xp_result["nivel_nuevo"]

        # Micro-premio
        if self.premio_parcial_id and self.premio_parcial:
            if self.premio_parcial.estado.value == "Bloqueado":
                self.premio_parcial.desbloquear()
                efectos["premio_parcial"] = self.premio_parcial.titulo

        # Meta padre
        if self.meta:
            efectos["meta_progreso"]  = self.meta.progreso_calculado
            meta_completada = self.meta.check_completar_y_otorgar_xp()
            efectos["meta_completada"] = meta_completada

            if meta_completada and self.meta.premio:
                efectos["premio_final"] = self.meta.premio.titulo

        db.session.commit()
        return efectos

    def to_dict(self):
        return {
            "id":               self.id,
            "titulo":           self.titulo,
            "recursos":         self.recursos,
            "obstaculos":       self.obstaculos,
            "soluciones":       self.soluciones,
            "estado":           self.estado.value,
            "meta_id":          self.meta_id,
            "premio_parcial_id": self.premio_parcial_id,
            "premio_parcial":   self.premio_parcial.to_dict() if self.premio_parcial else None,
            "fecha_completado": self.fecha_completado.isoformat() if self.fecha_completado else None,
            "created_at":       self.created_at.isoformat()       if self.created_at       else None,
        }

    def __repr__(self):
        return f"<Objetivo '{self.titulo}' | {self.estado.value}>"

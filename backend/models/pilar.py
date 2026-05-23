"""
MOSS - Modelo Pilar (Sistema RPG completo)
Evoluciona desde mock_pilares del Módulo 1.

Este modelo reemplaza la tabla mock_pilares.
MIGRACIÓN: Una vez activo, actualizar FK en:
  - Task.pilar_id        → apunta aquí
  - Meta.pilar_id        → apunta aquí
  - PilarEvaluacion.pilar_id → apunta aquí

Sistema de niveles RPG:
  Nivel 1: Supervivencia   (0    – 99   XP)
  Nivel 2: Estabilidad     (100  – 299  XP)
  Nivel 3: Crecimiento     (300  – 699  XP)
  Nivel 4: Libertad        (700  – 1499 XP)
  Nivel 5: Maestría        (1500 – 2999 XP)
  Nivel 6: Abundancia      (3000+       XP)

Conexiones del sistema:
  Pilar ◄── Meta[]            (1:N)
  Pilar ◄── PilarEvaluacion[] (1:N – snapshots trimestrales)
  Pilar ◄── Task[]            (1:N – tareas cotidianas)
  Pilar ──► Centro de Mando   (Widget: Rueda de la Vida)
"""

import uuid
from datetime import datetime
from backend.app import db


XP_POR_NIVEL = {
    1: 0,
    2: 100,
    3: 300,
    4: 700,
    5: 1500,
    6: 3000,
}

NOMBRE_NIVEL = {
    1: "Supervivencia",
    2: "Estabilidad",
    3: "Crecimiento",
    4: "Libertad",
    5: "Maestría",
    6: "Abundancia",
}

PILARES_OFICIALES = [
    "Espiritualidad",
    "Familia y Amigos",
    "Matrimonio",
    "Maternidad",
    "Finanzas",
    "Estudios",
    "Trabajo",
    "Imagen y Proyección",
    "Hogar",
    "Negocio",
    "Salud",
]


class Pilar(db.Model):
    __tablename__ = "pilares"

    id     = db.Column(db.String(36), primary_key=True,
                       default=lambda: str(uuid.uuid4()))
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    icono  = db.Column(db.String(50),  nullable=True)

    nivel_actual  = db.Column(db.Integer, default=1)
    xp_acumulado  = db.Column(db.Integer, default=0)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                             onupdate=datetime.utcnow)

    # ── Relaciones ORM ─────────────────────────────────────────────────────────
    metas = db.relationship("Meta", back_populates="pilar",
                            lazy="dynamic", cascade="all, delete-orphan")
    evaluaciones = db.relationship("PilarEvaluacion", back_populates="pilar",
                                   lazy="dynamic",
                                   order_by="PilarEvaluacion.fecha_evaluacion.desc()",
                                   cascade="all, delete-orphan")
    tareas = db.relationship("Task", back_populates="pilar",
                             lazy="dynamic", cascade="all, delete-orphan")

    # ── Propiedades calculadas ─────────────────────────────────────────────────
    @property
    def nombre_nivel(self):
        return NOMBRE_NIVEL.get(self.nivel_actual, "Maestría")

    @property
    def xp_para_siguiente_nivel(self):
        siguiente = self.nivel_actual + 1
        return XP_POR_NIVEL.get(siguiente, None)

    @property
    def xp_en_nivel_actual(self):
        xp_inicio_nivel = XP_POR_NIVEL.get(self.nivel_actual, 0)
        return self.xp_acumulado - xp_inicio_nivel

    @property
    def progreso_nivel(self):
        xp_siguiente = self.xp_para_siguiente_nivel
        if xp_siguiente is None:
            return 100
        xp_inicio = XP_POR_NIVEL.get(self.nivel_actual, 0)
        xp_en_nivel   = self.xp_acumulado - xp_inicio
        xp_necesario  = xp_siguiente - xp_inicio
        if xp_necesario <= 0:
            return 100
        return min(100, round((xp_en_nivel / xp_necesario) * 100))

    @property
    def ultima_evaluacion(self):
        return self.evaluaciones.first()

    @property
    def puntuacion_actual(self):
        ev = self.ultima_evaluacion
        return ev.puntuacion if ev else 5

    # ── Motor de XP ───────────────────────────────────────────────────────────
    def otorgar_xp(self, cantidad: int, fuente: str = "tarea") -> dict:
        nivel_anterior = self.nivel_actual
        self.xp_acumulado += cantidad
        self._actualizar_nivel()
        db.session.commit()

        nivel_nuevo  = self.nivel_actual
        subio_nivel  = nivel_nuevo > nivel_anterior

        return {
            "xp_ganado":     cantidad,
            "xp_total":      self.xp_acumulado,
            "nivel_anterior": nivel_anterior,
            "nivel_nuevo":   nivel_nuevo,
            "subio_nivel":   subio_nivel,
            "fuente":        fuente,
        }

    def _actualizar_nivel(self):
        nuevo_nivel = 1
        for nivel, xp_min in sorted(XP_POR_NIVEL.items(), reverse=True):
            if self.xp_acumulado >= xp_min:
                nuevo_nivel = nivel
                break
        self.nivel_actual = nuevo_nivel

    # ── Serialización ─────────────────────────────────────────────────────────
    def to_dict(self, include_evaluaciones=False):
        data = {
            "id":                    self.id,
            "nombre":                self.nombre,
            "icono":                 self.icono,
            "nivel_actual":          self.nivel_actual,
            "nombre_nivel":          self.nombre_nivel,
            "xp_acumulado":          self.xp_acumulado,
            "xp_para_siguiente":     self.xp_para_siguiente_nivel,
            "xp_en_nivel_actual":    self.xp_en_nivel_actual,
            "progreso_nivel":        self.progreso_nivel,
            "puntuacion_actual":     self.puntuacion_actual,
            "metas_activas":         self.metas.filter_by(estado="Activa").count(),
            "tareas_pendientes":     self.tareas.filter_by(estado="planificada").count(),
        }
        if include_evaluaciones:
            data["evaluaciones"] = [e.to_dict() for e in self.evaluaciones.limit(4).all()]
        return data

    def __repr__(self):
        return f"<Pilar '{self.nombre}' | Nv.{self.nivel_actual} | {self.xp_acumulado}XP>"

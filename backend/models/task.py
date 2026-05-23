"""
MOSS - Modelo Task (Tarea)
Versión Final Congelada — Todos los campos acordados incluidos.

Relaciones preparadas para módulos futuros:
- pilar_id → FK a tabla 'pilares' (Módulo: Rueda de la Vida)
- meta_id  → FK a tabla 'metas'   (Módulo: Planificación 12 Semanas)
- checkin_cancelacion_id → FK a 'daily_checkins' (Análisis de Datos)
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from backend.app import db


# ─── Enums ────────────────────────────────────────────────────────────────────

class TaskEstado(PyEnum):
    INBOX       = "inbox"
    PLANIFICADA = "planificada"
    COMPLETADA  = "completada"
    CANCELADA   = "cancelada"
    ELIMINADA   = "eliminada"

class TaskTipo(PyEnum):
    COTIDIANA   = "Cotidiana"
    ESTRATEGICA = "Estratégica"

class TaskDuracion(PyEnum):
    CORTA = "<3min"
    LARGA = ">3min"

class TaskContexto(PyEnum):
    CASA    = "Casa"
    TRABAJO = "Trabajo"
    FUERA   = "Fuera de casa"
    MOVIL   = "Desde el móvil"
    COMPU   = "Desde la compu"

class TaskFrecuencia(PyEnum):
    UNICA   = "Única"
    SEMANAL = "Semanal"
    MENSUAL = "Mensual"
    CADA_X  = "Cada X días"

class NivelEnergia(PyEnum):
    ALTA  = "Alta"
    MEDIA = "Media"
    BAJA  = "Baja"

class ImpactoEmocional(PyEnum):
    ME_DA_ENERGIA = "Me da energía"
    ME_DRENA      = "Me drena"

class MotivoCancelacion(PyEnum):
    SALUD_ENERGIA      = "Salud/Energía"
    PRIORIDAD_CAMBIADA = "Prioridad cambiada"
    CONFLICTO          = "Conflicto"
    OTRO               = "Otro"


# ─── Modelo Principal ─────────────────────────────────────────────────────────

class Task(db.Model):
    __tablename__ = "tasks"

    id     = db.Column(db.String(36), primary_key=True,
                       default=lambda: str(uuid.uuid4()))
    titulo = db.Column(db.String(500), nullable=False)

    estado             = db.Column(db.Enum(TaskEstado),
                                   default=TaskEstado.INBOX, nullable=False)
    fecha_creacion     = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_planificada  = db.Column(db.Date, nullable=True)
    fecha_completado   = db.Column(db.DateTime, nullable=True)

    tipo                    = db.Column(db.Enum(TaskTipo), nullable=True)
    duracion                = db.Column(db.Enum(TaskDuracion), nullable=True)
    contexto                = db.Column(db.Enum(TaskContexto), nullable=True)
    frecuencia              = db.Column(db.Enum(TaskFrecuencia),
                                        default=TaskFrecuencia.UNICA)
    recurrence_rule         = db.Column(db.String(200), nullable=True)

    nivel_energia_requerido = db.Column(db.Enum(NivelEnergia), nullable=True)
    impacto_emocional       = db.Column(db.Enum(ImpactoEmocional), nullable=True)

    is_urgent    = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)

    @property
    def eisenhower_label(self):
        if self.is_urgent and self.is_important:
            return "top"
        elif self.is_important and not self.is_urgent:
            return "media"
        elif self.is_urgent and not self.is_important:
            return "delegar"
        else:
            return "mantenimiento"

    @property
    def eisenhower_prioridad(self):
        orden = {"top": 1, "media": 2, "delegar": 3, "mantenimiento": 4}
        return orden.get(self.eisenhower_label, 4)

    es_evento_con_hora = db.Column(db.Boolean, default=False)
    hora_inicio        = db.Column(db.Time, nullable=True)

    fue_cancelado_por_energia  = db.Column(db.Boolean, default=False)
    fecha_cancelacion          = db.Column(db.DateTime, nullable=True)
    motivo_cancelacion         = db.Column(db.Enum(MotivoCancelacion),
                                           nullable=True)
    checkin_cancelacion_id     = db.Column(
        db.String(36),
        db.ForeignKey("daily_checkins.id"),
        nullable=True
    )

    # ── Relaciones FK ──────────────────────────────────────────────────────────
    pilar_id = db.Column(db.String(36), db.ForeignKey("pilares.id"),
                         nullable=True)
    meta_id  = db.Column(db.String(36), db.ForeignKey("metas.id"),
                         nullable=True)

    # ── Relaciones ORM ─────────────────────────────────────────────────────────
    checkin_cancelacion = db.relationship(
        "DailyCheckIn",
        foreign_keys=[checkin_cancelacion_id],
        back_populates="cancelaciones"
    )
    pilar = db.relationship("Pilar", back_populates="tareas")
    meta  = db.relationship("Meta", back_populates="tareas")

    # ── Métodos de Serialización ───────────────────────────────────────────────
    def to_dict(self):
        return {
            "id":                        self.id,
            "titulo":                    self.titulo,
            "estado":                    self.estado.value,
            "tipo":                      self.tipo.value if self.tipo else None,
            "duracion":                  self.duracion.value if self.duracion else None,
            "contexto":                  self.contexto.value if self.contexto else None,
            "frecuencia":                self.frecuencia.value if self.frecuencia else None,
            "recurrence_rule":           self.recurrence_rule,
            "nivel_energia_requerido":   self.nivel_energia_requerido.value if self.nivel_energia_requerido else None,
            "impacto_emocional":         self.impacto_emocional.value if self.impacto_emocional else None,
            "is_urgent":                 self.is_urgent,
            "is_important":              self.is_important,
            "eisenhower_label":          self.eisenhower_label,
            "es_evento_con_hora":        self.es_evento_con_hora,
            "hora_inicio":               self.hora_inicio.strftime("%H:%M") if self.hora_inicio else None,
            "fecha_creacion":            self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "fecha_planificada":         self.fecha_planificada.isoformat() if self.fecha_planificada else None,
            "fecha_completado":          self.fecha_completado.isoformat() if self.fecha_completado else None,
            "fue_cancelado_por_energia": self.fue_cancelado_por_energia,
            "fecha_cancelacion":         self.fecha_cancelacion.isoformat() if self.fecha_cancelacion else None,
            "motivo_cancelacion":        self.motivo_cancelacion.value if self.motivo_cancelacion else None,
            "pilar_id":                  self.pilar_id,
            "pilar_nombre":              self.pilar.nombre if self.pilar else None,
            "meta_id":                   self.meta_id,
            "meta_titulo":               self.meta.titulo if self.meta else None,
        }

    def __repr__(self):
        return f"<Task {self.id[:8]} | '{self.titulo[:30]}' | {self.estado.value}>"


"""
MOSS - Modelo PilarEvaluacion (La Rueda de la Vida)
Snapshot trimestral de cómo percibe el usuario cada pilar.
"""
import uuid
from datetime import date, datetime
from backend.app import db


class PilarEvaluacion(db.Model):
    __tablename__ = "pilar_evaluaciones"

    # ── Identidad ──────────────────────────────────────────────────────────────
    id = db.Column(db.String(36), primary_key=True,
                   default=lambda: str(uuid.uuid4()))
    pilar_id = db.Column(db.String(36), db.ForeignKey("pilares.id"),
                         nullable=False)

    # ── La evaluación ──────────────────────────────────────────────────────────
    puntuacion = db.Column(db.Integer, nullable=False)
    nota_personal = db.Column(db.Text, nullable=True)
    fecha_evaluacion = db.Column(db.Date, default=date.today, nullable=False)
    ciclo_numero = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relación inversa emparejada con Pilar.evaluaciones ────────────────────
    pilar = db.relationship(
        "Pilar",
        back_populates="evaluaciones",
        foreign_keys=[pilar_id]
    )

    # ── Propiedad calculada ────────────────────────────────────────────────────
    @property
    def gap(self):
        return 10 - self.puntuacion

    @property
    def etiqueta(self):
        if self.puntuacion <= 2:
            return "Descuidado"
        if self.puntuacion <= 4:
            return "Necesita atención"
        if self.puntuacion <= 6:
            return "En desarrollo"
        if self.puntuacion <= 8:
            return "Saludable"
        return "Equilibrado"

    # ── Serialización ──────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            "id": self.id,
            "pilar_id": self.pilar_id,
            "puntuacion": self.puntuacion,
            "gap": self.gap,
            "etiqueta": self.etiqueta,
            "nota_personal": self.nota_personal,
            "fecha_evaluacion": self.fecha_evaluacion.isoformat(),
            "ciclo_numero": self.ciclo_numero,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Evaluacion Pilar:{self.pilar_id} | {self.puntuacion}/10 | {self.fecha_evaluacion}>"

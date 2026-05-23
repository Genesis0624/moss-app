"""
MOSS - Modelo DailyCheckIn (Check-in Diario)
Versión Final Congelada.

Este modelo actúa como el "termostato" del sistema:
su combinación mood + energía determina el modo del Dashboard
(Rendimiento, Normal, Protección) y filtra las tareas visibles.
"""

import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from backend.app import db


# ─── Enums ────────────────────────────────────────────────────────────────────

class MoodEnum(PyEnum):
    # Grupo Alto Rendimiento → Dashboard modo "rendimiento"
    EUFORICA  = "eufórica"
    FELIZ     = "feliz"
    PODEROSA  = "poderosa"
    # Neutro → Dashboard modo "normal"
    BIEN      = "bien"
    # Grupo Protección → Dashboard modo "protección"
    APAGADA   = "apagada"
    CANSADA   = "cansada"
    ESTRESADA = "estresada"
    ENFERMA   = "enferma"

class EnergiaEnum(PyEnum):
    ALTA  = "Alta"
    MEDIA = "Media"
    BAJA  = "Baja"


# ─── Modelo ───────────────────────────────────────────────────────────────────

class DailyCheckIn(db.Model):
    __tablename__ = "daily_checkins"

    id         = db.Column(db.String(36), primary_key=True,
                           default=lambda: str(uuid.uuid4()))
    fecha      = db.Column(db.Date, default=date.today,
                           unique=True, nullable=False)
    mood       = db.Column(db.Enum(MoodEnum), nullable=False)
    energia    = db.Column(db.Enum(EnergiaEnum), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Lógica de Modo ────────────────────────────────────────────────────────

    MOODS_RENDIMIENTO = {"eufórica", "feliz", "poderosa"}
    MOODS_PROTECCION  = {"apagada", "cansada", "estresada", "enferma"}

    @property
    def dashboard_mode(self):
        """
        Calcula el modo del dashboard combinando mood + energía.

        Matriz de decisión:
        ┌──────────────┬──────┬────────┬──────┐
        │              │ Alta │ Media  │ Baja │
        ├──────────────┼──────┼────────┼──────┤
        │ Eufórica     │  R   │   R    │  N   │
        │ Feliz        │  R   │   R    │  N   │
        │ Poderosa     │  R   │   R    │  N   │
        │ Bien         │  N   │   N    │  N   │
        │ Apagada      │  N   │   P    │  P   │
        │ Cansada      │  N   │   P    │  P   │
        │ Estresada    │  N   │   P    │  P   │
        │ Enferma      │  N   │   P    │  P   │
        └──────────────┴──────┴────────┴──────┘
        R = rendimiento | P = protección | N = normal
        """
        mood_val    = self.mood.value
        energia_val = self.energia.value

        mood_alto  = mood_val in self.MOODS_RENDIMIENTO
        mood_bajo  = mood_val in self.MOODS_PROTECCION
        energia_alta = energia_val in ("Alta", "Media")
        energia_baja = energia_val in ("Baja", "Media")

        if mood_alto and energia_alta:
            return "rendimiento"
        elif mood_bajo and energia_baja:
            return "proteccion"
        else:
            return "normal"

    @property
    def mensaje_bienvenida(self):
        """Mensaje personalizado según el estado del día."""
        mensajes = {
            "rendimiento": "¡Estás en tu mejor momento hoy! 🚀 Tienes luz verde para atacar todo.",
            "normal":      "Un día tranquilo. Avanza a tu ritmo. 🌿",
            "proteccion":  "Hoy nos cuidamos. El sistema te protege. 💛",
        }
        return mensajes[self.dashboard_mode]

    def to_dict(self):
        return {
            "id":                self.id,
            "fecha":             self.fecha.isoformat(),
            "mood":              self.mood.value,
            "energia":           self.energia.value,
            "dashboard_mode":    self.dashboard_mode,
            "mensaje_bienvenida": self.mensaje_bienvenida,
            "created_at":        self.created_at.isoformat(),
        }

    def __repr__(self):
        return (f"<CheckIn {self.fecha} | "
                f"{self.mood.value} | {self.energia.value} | "
                f"Modo: {self.dashboard_mode}>")

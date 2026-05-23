"""
MOSS - Datos Mock para Pilares y Metas
Tablas temporales que serán reemplazadas por los modelos reales
"""

import uuid
from backend.app import db


class MockPilar(db.Model):
    __tablename__ = "mock_pilares"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = db.Column(db.String(100), nullable=False, unique=True)

    def __init__(self, nombre: str):
        self.nombre = nombre

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}

    def __repr__(self):
        return f"<Pilar: {self.nombre}>"


class MockMeta(db.Model):
    __tablename__ = "mock_metas"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre = db.Column(db.String(200), nullable=False)

    def __init__(self, nombre: str):
        self.nombre = nombre

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}

    def __repr__(self):
        return f"<Meta: {self.nombre}>"

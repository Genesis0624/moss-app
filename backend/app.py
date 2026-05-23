"""
MOSS - My Operating System
Backend Entry Point (Flask)
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import logging

db = SQLAlchemy()


def create_app(config_name="development"):
    app = Flask(__name__)
    CORS(app)

    # ─── Configuración ─────────────────────────────────────────────────────────
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///moss_dev.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "moss-dev-secret-2024")

    # ─── Inicializar extensiones ────────────────────────────────────────────────
    db.init_app(app)

    # ─── Rutas básicas ──────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return "Bienvenida a MOSS 🚀"

    # ─── Registrar Blueprints (Rutas) ───────────────────────────────────────────
    # Importar blueprints dentro de create_app evita problemas de import circular
    from backend.routes.tasks import tasks_bp
    from backend.routes.checkin import checkin_bp

    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(checkin_bp, url_prefix="/api/checkin")

    # ─── Crear tablas y seed en primera ejecución ───────────────────────────────
    with app.app_context():
        db.create_all()
        try:
            _seed_mock_data()
        except Exception as e:
            # Loguea el error pero no rompe el arranque del servidor
            logging.exception("Error al insertar datos mock: %s", e)

    return app


def _seed_mock_data():
    """
    Inserta datos de prueba para Pilares y Metas.
    Importar los modelos aquí evita import circular al inicializar db.
    """
    from backend.models.mock_data import MockPilar, MockMeta

    # Asegurarse de que los modelos tienen el atributo query antes de usarlo
    if hasattr(MockPilar, "query") and MockPilar.query.count() == 0:
        pilares = [
            "Espiritualidad", "Familia y Amigos", "Matrimonio",
            "Maternidad", "Finanzas", "Estudios",
            "Trabajo", "Imagen y Proyección", "Hogar",
            "Negocio", "Salud"
        ]
        for nombre in pilares:
            db.session.add(MockPilar(nombre=nombre))

    if hasattr(MockMeta, "query") and MockMeta.query.count() == 0:
        metas_mock = [
            "Meta Q1: Salud y Bienestar",
            "Meta Q1: Crecimiento Negocio",
            "Meta Q1: Finanzas Personales",
            "Meta Q2: Estudios Ingeniería",
        ]
        for nombre in metas_mock:
            db.session.add(MockMeta(nombre=nombre))

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)

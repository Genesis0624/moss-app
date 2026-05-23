"""
MOSS - My Operating System
Backend Entry Point (Flask) — v3
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os

db = SQLAlchemy()

def create_app(config_name="development"):
    app = Flask(__name__)
    CORS(app)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///moss_dev.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "moss-dev-secret-2024")
    app.config["UPLOAD_FOLDER"] = os.path.join("frontend", "uploads")

    db.init_app(app)

    # ── Blueprints ──────────────────────────────────────────────────────────
    from backend.routes.tasks   import tasks_bp
    from backend.routes.checkin import checkin_bp
    from backend.routes.pilares import pilares_bp
    from backend.routes.metas   import metas_bp

    app.register_blueprint(tasks_bp,   url_prefix="/api/tasks")
    app.register_blueprint(checkin_bp, url_prefix="/api/checkin")
    app.register_blueprint(pilares_bp, url_prefix="/api/pilares")
    app.register_blueprint(metas_bp,   url_prefix="/api/metas")

    with app.app_context():
        db.create_all()
        _seed_data()

    return app


def _seed_data():
    """Crea los 11 pilares oficiales si no existen."""
    from backend.routes.pilares import _seed_pilares_oficiales
    _seed_pilares_oficiales()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
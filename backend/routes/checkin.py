"""
MOSS - Rutas API para Check-in Diario
Blueprint: /api/checkin

Endpoints:
  GET  /api/checkin/today        → Check-in de hoy (o null si no existe)
  POST /api/checkin/             → Crear check-in del día
  GET  /api/checkin/dashboard    → Dashboard completo filtrado por check-in de hoy
"""

from datetime import date
from flask import Blueprint, request, jsonify
from backend.app import db
from backend.models.daily_checkin import DailyCheckIn, MoodEnum, EnergiaEnum
from backend.logic.dashboard_filter import get_dashboard_data

checkin_bp = Blueprint("checkin", __name__)


@checkin_bp.route("/today", methods=["GET"])
def get_today_checkin():
    """
    Retorna el check-in de hoy si existe.
    El frontend usa este endpoint como Gatekeeper:
    - Si retorna null → mostrar modal de bienvenida
    - Si retorna datos → ir directo al Dashboard
    """
    checkin = DailyCheckIn.query.filter_by(fecha=date.today()).first()

    if not checkin:
        return jsonify({
            "exists":  False,
            "checkin": None,
            "message": "No hay check-in para hoy. Completa tu estado para comenzar."
        })

    return jsonify({
        "exists":  True,
        "checkin": checkin.to_dict()
    })


@checkin_bp.route("/", methods=["POST"])
def create_checkin():
    """
    Crear el check-in del día.
    Solo se puede crear uno por día (unique constraint en fecha).
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibieron datos."}), 400

    # Validar mood
    mood_val = data.get("mood")
    if not mood_val:
        return jsonify({"error": "El campo 'mood' es obligatorio."}), 400
    try:
        mood = MoodEnum(mood_val)
    except ValueError:
        valores_validos = [e.value for e in MoodEnum]
        return jsonify({
            "error":          f"Mood inválido: '{mood_val}'.",
            "valores_validos": valores_validos
        }), 400

    # Validar energía
    energia_val = data.get("energia")
    if not energia_val:
        return jsonify({"error": "El campo 'energia' es obligatorio."}), 400
    try:
        energia = EnergiaEnum(energia_val)
    except ValueError:
        return jsonify({
            "error":          f"Energía inválida: '{energia_val}'.",
            "valores_validos": [e.value for e in EnergiaEnum]
        }), 400

    # Verificar si ya existe check-in hoy
    existente = DailyCheckIn.query.filter_by(fecha=date.today()).first()
    if existente:
        return jsonify({
            "error":   "Ya existe un check-in para hoy.",
            "checkin": existente.to_dict()
        }), 409

    checkin = DailyCheckIn(mood=mood, energia=energia)
    db.session.add(checkin)
    db.session.commit()

    return jsonify({
        "success": True,
        "checkin": checkin.to_dict(),
        "message": checkin.mensaje_bienvenida
    }), 201


@checkin_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
    """
    Endpoint principal del Dashboard.
    Retorna los 3 bloques de tareas filtradas según el check-in de hoy.

    Si no hay check-in → retorna señal para mostrar el modal.
    """
    checkin = DailyCheckIn.query.filter_by(fecha=date.today()).first()

    if not checkin:
        return jsonify({
            "needs_checkin": True,
            "message":       "Completa tu check-in diario para ver el dashboard."
        }), 200

    dashboard_data = get_dashboard_data(checkin)

    return jsonify({
        "needs_checkin": False,
        "dashboard":     dashboard_data
    })

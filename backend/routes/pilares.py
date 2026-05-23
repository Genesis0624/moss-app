"""
MOSS - Rutas API para Pilares, Evaluaciones y Motor de Recomendación
Blueprint: /api/pilares

Endpoints:
  GET    /api/pilares/                      → Todos los pilares con estado RPG
  GET    /api/pilares/<id>                  → Pilar con evaluaciones
  POST   /api/pilares/<id>/evaluacion       → Registrar evaluación trimestral
  GET    /api/pilares/rueda                 → Datos para el gráfico radar
  POST   /api/pilares/evaluar-todos         → Evaluación masiva (inicio de ciclo)
  POST   /api/pilares/<id>/xp               → Otorgar XP manualmente (debug/admin)

  GET    /api/metas/recomendadas            → Motor de Recomendación
"""

from datetime import date
from flask import Blueprint, request, jsonify
from backend.app import db
from backend.models.pilar            import Pilar, PILARES_OFICIALES
from backend.models.pilar_evaluacion import PilarEvaluacion

pilares_bp = Blueprint("pilares", __name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PILARES
# ═══════════════════════════════════════════════════════════════════════════════

@pilares_bp.route("/", methods=["GET"])
def get_pilares():
    """
    Todos los pilares con su estado RPG actual.
    Incluye nivel, XP, puntuación de la Rueda de la Vida.
    """
    pilares = Pilar.query.order_by(Pilar.nombre).all()

    # Si no existen, sembrar los 11 pilares oficiales
    if not pilares:
        pilares = _seed_pilares_oficiales()

    return jsonify({
        "count":   len(pilares),
        "pilares": [p.to_dict() for p in pilares]
    })


@pilares_bp.route("/<pilar_id>", methods=["GET"])
def get_pilar(pilar_id):
    """Detalle del pilar incluyendo historial de evaluaciones."""
    pilar = Pilar.query.get_or_404(pilar_id)
    return jsonify(pilar.to_dict(include_evaluaciones=True))


@pilares_bp.route("/rueda", methods=["GET"])
def get_rueda_de_vida():
    """
    Datos formateados para el gráfico radar de la Rueda de la Vida.
    El frontend (Chart.js / D3) los usará directamente.

    Retorna:
      {
        "labels": ["Salud", "Finanzas", ...],
        "puntuaciones": [7, 3, ...],
        "niveles": [2, 1, ...],
        "colores": ["#b8cc7a", "#e05c5c", ...]
      }
    """
    pilares = Pilar.query.order_by(Pilar.nombre).all()
    if not pilares:
        pilares = _seed_pilares_oficiales()

    labels       = []
    puntuaciones = []
    niveles      = []
    colores      = []

    for p in pilares:
        labels.append(p.nombre)
        puntuaciones.append(p.puntuacion_actual)
        niveles.append(p.nivel_actual)
        # Color basado en la puntuación (rojo → ámbar → verde)
        pts = p.puntuacion_actual
        if pts <= 3:   color = "#e05c5c"   # rojo: descuidado
        elif pts <= 6: color = "#d4a85a"   # ámbar: en desarrollo
        else:          color = "#b8cc7a"   # verde: saludable
        colores.append(color)

    return jsonify({
        "labels":        labels,
        "puntuaciones":  puntuaciones,
        "niveles":       niveles,
        "colores":       colores,
        "promedio":      round(sum(puntuaciones) / len(puntuaciones), 1) if puntuaciones else 0,
    })


@pilares_bp.route("/<pilar_id>/evaluacion", methods=["POST"])
def crear_evaluacion(pilar_id):
    """
    Registrar la evaluación trimestral de un pilar.
    Esta puntuación alimenta el Motor de Recomendación.
    """
    Pilar.query.get_or_404(pilar_id)
    data = request.get_json() or {}

    puntuacion = data.get("puntuacion")
    if puntuacion is None:
        return jsonify({"error": "El campo 'puntuacion' es obligatorio."}), 400

    try:
        puntuacion = int(puntuacion)
        if not (1 <= puntuacion <= 10):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "La puntuación debe ser un número entero del 1 al 10."}), 400

    evaluacion = PilarEvaluacion(
        pilar_id         = pilar_id,
        puntuacion       = puntuacion,
        nota_personal    = data.get("nota_personal"),
        ciclo_numero     = data.get("ciclo_numero"),
        fecha_evaluacion = date.fromisoformat(data["fecha"]) if data.get("fecha") else date.today(),
    )
    db.session.add(evaluacion)
    db.session.commit()

    pilar = Pilar.query.get(pilar_id)
    return jsonify({
        "success":   True,
        "evaluacion": evaluacion.to_dict(),
        "pilar":     pilar.to_dict(),
    }), 201


@pilares_bp.route("/evaluar-todos", methods=["POST"])
def evaluar_todos():
    """
    Evaluación masiva — usada al inicio de cada ciclo de 12 semanas.
    Recibe un array de { pilar_id, puntuacion, nota_personal }.
    """
    data = request.get_json() or {}
    evaluaciones_data = data.get("evaluaciones", [])

    if not evaluaciones_data:
        return jsonify({"error": "Se requiere un array 'evaluaciones'."}), 400

    ciclo_numero = data.get("ciclo_numero")
    creadas = []

    for ev_data in evaluaciones_data:
        pilar_id   = ev_data.get("pilar_id")
        puntuacion = ev_data.get("puntuacion")

        if not pilar_id or puntuacion is None:
            continue
        if not (1 <= int(puntuacion) <= 10):
            continue

        ev = PilarEvaluacion(
            pilar_id      = pilar_id,
            puntuacion    = int(puntuacion),
            nota_personal = ev_data.get("nota_personal"),
            ciclo_numero  = ciclo_numero,
        )
        db.session.add(ev)
        creadas.append(pilar_id)

    db.session.commit()

    return jsonify({
        "success":          True,
        "evaluaciones_creadas": len(creadas),
        "pilares_evaluados":    creadas,
        "message": "Rueda de la Vida actualizada. El Motor de Recomendación está activo."
    }), 201


@pilares_bp.route("/<pilar_id>/xp", methods=["POST"])
def otorgar_xp_manual(pilar_id):
    """Otorgar XP manualmente (útil para debug y administración)."""
    pilar = Pilar.query.get_or_404(pilar_id)
    data  = request.get_json() or {}

    cantidad = data.get("cantidad", 10)
    fuente   = data.get("fuente", "manual")

    resultado = pilar.otorgar_xp(int(cantidad), fuente=fuente)
    return jsonify({
        "success": True,
        "resultado": resultado,
        "pilar":   pilar.to_dict()
    })


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE RECOMENDACIÓN DE METAS
# ═══════════════════════════════════════════════════════════════════════════════

@pilares_bp.route("/metas/recomendadas", methods=["GET"])
def get_metas_recomendadas():
    """
    MOTOR DE RECOMENDACIÓN DE METAS

    Algoritmo:
      Para cada Meta activa:
        1. Obtener la última PilarEvaluacion del pilar de la meta
        2. Calcular gap = 10 - puntuacion_pilar
        3. Calcular score = gap * prioridad_impacto
        4. Ordenar metas por score DESC

    Interpretación del score:
      30–45 → Prioridad de Balance (pilar muy descuidado + alto impacto)
      20–29 → Alta Relevancia
      10–19 → Recomendada
      0–9   → Normal (pilar ya saludable)

    Parámetros opcionales:
      ?pilar_id=<uuid>  → filtrar por pilar específico
      ?limite=10        → máximo de resultados (default: todas)

    Ejemplo de respuesta:
      {
        "metas": [
          {
            "id": "...",
            "titulo": "Crear fondo de emergencia",
            "pilar_nombre": "Finanzas",
            "puntuacion_pilar": 2,
            "gap": 8,
            "prioridad_impacto": 5,
            "score_recomendacion": 40,
            "etiqueta_recomendacion": "🚨 Prioridad de Balance",
            ...
          }
        ]
      }
    """
    from backend.models.meta_v3 import Meta, MetaEstado

    # Solo metas activas son candidatas a recomendación
    query = Meta.query.filter_by(estado=MetaEstado.ACTIVA)

    if pilar_id := request.args.get("pilar_id"):
        query = query.filter_by(pilar_id=pilar_id)

    limite = int(request.args.get("limite", 50))
    metas  = query.all()

    # Calcular scores y ordenar en Python
    # (más flexible que ORDER BY en SQL para propiedades calculadas)
    metas_con_score = []

    for meta in metas:
        score = meta.score_recomendacion
        metas_con_score.append({
            **meta.to_dict(include_score=True),
            # Datos extra para el frontend
            "puntuacion_pilar": meta.pilar.puntuacion_actual if meta.pilar else 5,
            "gap":              (10 - (meta.pilar.puntuacion_actual if meta.pilar else 5)),
        })

    # Ordenar por score descendente
    metas_con_score.sort(key=lambda m: m["score_recomendacion"], reverse=True)

    # Aplicar límite
    metas_con_score = metas_con_score[:limite]

    # Estadísticas del resultado
    alta_prioridad = [m for m in metas_con_score if m["score_recomendacion"] >= 20]
    pilar_mas_urgente = None

    if metas_con_score:
        # El pilar con mayor gap promedio entre las top metas
        from collections import Counter
        pilares_top = [m["pilar_nombre"] for m in metas_con_score[:5] if m["pilar_nombre"]]
        if pilares_top:
            pilar_mas_urgente = Counter(pilares_top).most_common(1)[0][0]

    return jsonify({
        "total":             len(metas_con_score),
        "alta_prioridad":    len(alta_prioridad),
        "pilar_mas_urgente": pilar_mas_urgente,
        "metas":             metas_con_score,
        "algoritmo": {
            "formula":      "score = (10 - puntuacion_pilar) * prioridad_impacto",
            "rango":        "0 – 45",
            "descripcion":  "Prioriza metas en pilares descuidados con alto impacto"
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER — Sembrar pilares oficiales
# ═══════════════════════════════════════════════════════════════════════════════

def _seed_pilares_oficiales():
    """
    Crear los 11 pilares oficiales de MOSS si no existen.
    Se llama automáticamente si la tabla está vacía.
    Reemplaza la función _seed_mock_data() del Módulo 1.
    """
    iconos_por_pilar = {
        "Espiritualidad":      "ti-star",
        "Familia y Amigos":    "ti-users",
        "Matrimonio":          "ti-ring",
        "Maternidad":          "ti-baby-carriage",
        "Finanzas":            "ti-coin",
        "Estudios":            "ti-book",
        "Trabajo":             "ti-briefcase",
        "Imagen y Proyección": "ti-camera",
        "Hogar":               "ti-home",
        "Negocio":             "ti-rocket",
        "Salud":               "ti-heart",
    }

    pilares_creados = []
    for nombre in PILARES_OFICIALES:
        if not Pilar.query.filter_by(nombre=nombre).first():
            p = Pilar(nombre=nombre, icono=iconos_por_pilar.get(nombre))
            db.session.add(p)
            pilares_creados.append(p)

    db.session.commit()
    return Pilar.query.order_by(Pilar.nombre).all()
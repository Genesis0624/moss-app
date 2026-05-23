"""
MOSS - Rutas API para Metas, Objetivos y Premios (v3)
Blueprint: /api/metas

Actualizado para usar los modelos v3 (pilar.py, meta_v3.py, objetivo_v3.py, premio_v3.py)

Endpoints:
  GET    /api/metas/                              → Todas las metas
  POST   /api/metas/                              → Crear meta
  GET    /api/metas/<id>                          → Detalle con objetivos
  PUT    /api/metas/<id>                          → Editar meta
  DELETE /api/metas/<id>                          → Eliminar meta
  POST   /api/metas/<id>/cover                    → Subir foto de portada
  GET    /api/metas/<id>/progreso                 → Progreso calculado

  POST   /api/metas/<id>/objetivos/               → Agregar objetivo
  PUT    /api/metas/<meta_id>/objetivos/<obj_id>  → Editar objetivo
  POST   /api/metas/<meta_id>/objetivos/<obj_id>/completar → Completar objetivo

  GET    /api/metas/premios/                      → Lista de premios
  POST   /api/metas/premios/                      → Crear premio
  PUT    /api/metas/premios/<id>                  → Editar premio
  POST   /api/metas/premios/<id>/obtener          → Marcar como obtenido
"""

import os
import uuid
from datetime import date
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from backend.app import db
from backend.models.meta_v3     import Meta, MetaEstado, MetaPlazo
from backend.models.objetivo_v3 import Objetivo, ObjetivoEstado
from backend.models.premio_v3   import Premio, PremioEstado

metas_bp = Blueprint("metas", __name__)

# ── Configuración de uploads ──────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_upload_folder():
    folder = os.path.join("frontend", "uploads", "covers")
    os.makedirs(folder, exist_ok=True)
    return folder


# ═══════════════════════════════════════════════════════════════════════════════
# METAS
# ═══════════════════════════════════════════════════════════════════════════════

@metas_bp.route("/", methods=["GET"])
def get_metas():
    query = Meta.query

    if estado := request.args.get("estado"):
        try:    query = query.filter_by(estado=MetaEstado(estado))
        except ValueError: pass

    if pilar_id := request.args.get("pilar_id"):
        query = query.filter_by(pilar_id=pilar_id)

    if plazo := request.args.get("plazo"):
        try:    query = query.filter_by(plazo=MetaPlazo(plazo))
        except ValueError: pass

    metas = query.order_by(Meta.created_at.desc()).all()
    return jsonify({
        "count": len(metas),
        "metas": [m.to_dict() for m in metas]
    })


@metas_bp.route("/", methods=["POST"])
def create_meta():
    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        file = request.files.get("foto_portada")
    else:
        data = request.get_json() or {}
        file = None

    if not data.get("titulo"):
        return jsonify({"error": "El campo 'titulo' es obligatorio."}), 400
    if not data.get("pilar_id"):
        return jsonify({"error": "El campo 'pilar_id' es obligatorio."}), 400

    meta = Meta(
        titulo   = data["titulo"].strip(),
        pilar_id = data["pilar_id"],
    )
    _update_meta_fields(meta, data)

    if file and file.filename:
        foto_url = _save_cover_image(file)
        if foto_url:
            meta.foto_portada_url = foto_url
        else:
            return jsonify({"error": "Tipo de archivo no permitido."}), 400

    db.session.add(meta)
    db.session.commit()

    return jsonify({
        "success": True,
        "meta":    meta.to_dict(),
        "message": f"Meta '{meta.titulo}' creada."
    }), 201


@metas_bp.route("/<meta_id>", methods=["GET"])
def get_meta(meta_id):
    meta = Meta.query.get_or_404(meta_id)
    return jsonify(meta.to_dict(include_objetivos=True))


@metas_bp.route("/<meta_id>", methods=["PUT"])
def update_meta(meta_id):
    meta = Meta.query.get_or_404(meta_id)

    if request.content_type and "multipart" in request.content_type:
        data = request.form.to_dict()
        file = request.files.get("foto_portada")
    else:
        data = request.get_json() or {}
        file = None

    if "titulo" in data and data["titulo"].strip():
        meta.titulo = data["titulo"].strip()

    _update_meta_fields(meta, data)

    if file and file.filename:
        foto_url = _save_cover_image(file)
        if foto_url:
            _delete_old_cover(meta.foto_portada_url)
            meta.foto_portada_url = foto_url

    db.session.commit()
    return jsonify({"success": True, "meta": meta.to_dict()})


@metas_bp.route("/<meta_id>", methods=["DELETE"])
def delete_meta(meta_id):
    meta = Meta.query.get_or_404(meta_id)
    _delete_old_cover(meta.foto_portada_url)
    db.session.delete(meta)
    db.session.commit()
    return jsonify({"success": True, "message": f"Meta '{meta.titulo}' eliminada."})


@metas_bp.route("/<meta_id>/cover", methods=["POST"])
def upload_cover(meta_id):
    meta = Meta.query.get_or_404(meta_id)
    file = request.files.get("foto_portada")

    if not file or not file.filename:
        return jsonify({"error": "No se recibió ningún archivo."}), 400

    foto_url = _save_cover_image(file)
    if not foto_url:
        return jsonify({"error": "Tipo de archivo no permitido."}), 400

    _delete_old_cover(meta.foto_portada_url)
    meta.foto_portada_url = foto_url
    db.session.commit()

    return jsonify({
        "success":          True,
        "foto_portada_url": foto_url,
        "message":          "Imagen actualizada."
    })


@metas_bp.route("/<meta_id>/progreso", methods=["GET"])
def get_progreso(meta_id):
    meta = Meta.query.get_or_404(meta_id)
    return jsonify({
        "meta_id":               meta_id,
        "progreso":              meta.progreso_calculado,
        "objetivos_completados": meta.objetivos_completados,
        "objetivos_total":       meta.objetivos_total,
        "estado":                meta.estado.value,
        "premio_desbloqueado":   meta.premio.estado.value if meta.premio else None,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# OBJETIVOS
# ═══════════════════════════════════════════════════════════════════════════════

@metas_bp.route("/<meta_id>/objetivos/", methods=["POST"])
def create_objetivo(meta_id):
    Meta.query.get_or_404(meta_id)
    data = request.get_json() or {}

    if not data.get("titulo"):
        return jsonify({"error": "El campo 'titulo' es obligatorio."}), 400

    obj = Objetivo(
        titulo     = data["titulo"].strip(),
        meta_id    = meta_id,
        recursos   = data.get("recursos"),
        obstaculos = data.get("obstaculos"),
        soluciones = data.get("soluciones"),
    )

    db.session.add(obj)
    db.session.commit()

    return jsonify({
        "success":  True,
        "objetivo": obj.to_dict(),
        "message":  "Objetivo creado."
    }), 201


@metas_bp.route("/<meta_id>/objetivos/<obj_id>", methods=["PUT"])
def update_objetivo(meta_id, obj_id):
    obj  = Objetivo.query.filter_by(id=obj_id, meta_id=meta_id).first_or_404()
    data = request.get_json() or {}

    for field in ("titulo", "recursos", "obstaculos", "soluciones"):
        if field in data:
            setattr(obj, field, data[field])

    if "estado" in data:
        try:    obj.estado = ObjetivoEstado(data["estado"])
        except ValueError: pass

    db.session.commit()
    return jsonify({"success": True, "objetivo": obj.to_dict()})


@metas_bp.route("/<meta_id>/objetivos/<obj_id>/completar", methods=["POST"])
def completar_objetivo(meta_id, obj_id):
    """
    Completar un objetivo.
    Dispara automáticamente:
      - +50 XP al Pilar
      - Verificación de meta al 100% (+200 XP + desbloqueo de premio)
    """
    obj = Objetivo.query.filter_by(id=obj_id, meta_id=meta_id).first_or_404()

    if obj.estado == ObjetivoEstado.COMPLETADO:
        return jsonify({"error": "Este objetivo ya está completado."}), 400

    efectos = obj.completar()
    meta    = Meta.query.get(meta_id)

    return jsonify({
        "success":             True,
        "objetivo":            obj.to_dict(),
        "meta_progreso":       efectos.get("meta_progreso", 0),
        "meta_completada":     efectos.get("meta_completada", False),
        "xp_ganado":           efectos.get("xp_ganado", 0),
        "nivel_subio":         efectos.get("nivel_subio", False),
        "nivel_nuevo":         efectos.get("nivel_nuevo"),
        "premio_parcial":      efectos.get("premio_parcial"),
        "premio_final":        efectos.get("premio_final"),
        "message": "¡Objetivo completado!" + (
            f" 🎉 ¡Premio '{meta.premio.titulo}' desbloqueado!"
            if meta and meta.premio and meta.premio.estado == PremioEstado.DESBLOQUEADO
            else f" +{efectos.get('xp_ganado', 0)} XP"
        )
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PREMIOS
# ═══════════════════════════════════════════════════════════════════════════════

@metas_bp.route("/premios/", methods=["GET"])
def get_premios():
    estado = request.args.get("estado")
    query  = Premio.query
    if estado:
        try:    query = query.filter_by(estado=PremioEstado(estado))
        except ValueError: pass
    premios = query.order_by(Premio.created_at.desc()).all()
    return jsonify({"count": len(premios), "premios": [p.to_dict() for p in premios]})


@metas_bp.route("/premios/", methods=["POST"])
def create_premio():
    data = request.get_json() or {}
    if not data.get("titulo"):
        return jsonify({"error": "El campo 'titulo' es obligatorio."}), 400

    premio = Premio(
        titulo           = data["titulo"].strip(),
        descripcion      = data.get("descripcion"),
        costo_financiero = data.get("costo_financiero"),
    )
    db.session.add(premio)
    db.session.commit()

    return jsonify({"success": True, "premio": premio.to_dict()}), 201


@metas_bp.route("/premios/<premio_id>", methods=["PUT"])
def update_premio(premio_id):
    premio = Premio.query.get_or_404(premio_id)
    data   = request.get_json() or {}

    for field in ("titulo", "descripcion", "costo_financiero"):
        if field in data:
            setattr(premio, field, data[field])

    db.session.commit()
    return jsonify({"success": True, "premio": premio.to_dict()})


@metas_bp.route("/premios/<premio_id>/obtener", methods=["POST"])
def marcar_obtenido(premio_id):
    premio = Premio.query.get_or_404(premio_id)

    if premio.estado != PremioEstado.DESBLOQUEADO:
        return jsonify({
            "error": f"El premio debe estar Desbloqueado. Estado actual: {premio.estado.value}"
        }), 400

    premio.marcar_obtenido()
    return jsonify({
        "success": True,
        "premio":  premio.to_dict(),
        "message": f"🎁 ¡Felicidades! '{premio.titulo}' marcado como obtenido."
    })


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS PRIVADOS
# ═══════════════════════════════════════════════════════════════════════════════

def _update_meta_fields(meta, data):
    if "icono" in data:
        meta.icono = data["icono"]

    if "descripcion" in data:
        meta.descripcion = data["descripcion"]

    if "plazo" in data and data["plazo"]:
        try:    meta.plazo = MetaPlazo(data["plazo"])
        except ValueError: pass

    if "estado" in data and data["estado"]:
        try:    meta.estado = MetaEstado(data["estado"])
        except ValueError: pass

    if "premio_id" in data:
        meta.premio_id = data["premio_id"] or None

    if "prioridad_impacto" in data:
        try:    meta.prioridad_impacto = int(data["prioridad_impacto"])
        except (ValueError, TypeError): pass

    if "fecha_inicio" in data and data["fecha_inicio"]:
        meta.fecha_inicio = date.fromisoformat(data["fecha_inicio"])

    if "fecha_limite" in data and data["fecha_limite"]:
        meta.fecha_limite = date.fromisoformat(data["fecha_limite"])


def _save_cover_image(file):
    if not file or not allowed_file(file.filename):
        return None
    ext      = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(get_upload_folder(), filename)
    file.save(filepath)
    return f"uploads/covers/{filename}"


def _delete_old_cover(foto_url):
    if not foto_url:
        return
    try:
        full_path = os.path.join("frontend", foto_url)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass
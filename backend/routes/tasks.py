"""
MOSS - Rutas API para Tareas
Blueprint: /api/tasks

Endpoints:
  GET    /api/tasks/inbox          → Tareas para el Gestor Nocturno
  GET    /api/tasks/               → Todas las tareas (con filtros)
  POST   /api/tasks/               → Crear tarea (captura rápida FAB)
  GET    /api/tasks/<id>           → Detalle de tarea
  PUT    /api/tasks/<id>           → Editar tarea completa (Task Manager)
  DELETE /api/tasks/<id>           → Soft delete
  POST   /api/tasks/<id>/complete  → Acción: Completar
  POST   /api/tasks/<id>/inbox     → Acción: Devolver al inbox
  POST   /api/tasks/<id>/cancel    → Acción: Cancelar (Modo Protección)
  POST   /api/tasks/<id>/reschedule→ Acción: Reprogramar
  GET    /api/tasks/selectors      → Datos para selectores del formulario
"""

from datetime import datetime, date
from flask import Blueprint, request, jsonify
from backend.app import db
from backend.models.task import (
    Task, TaskEstado, TaskTipo, TaskDuracion, TaskContexto,
    TaskFrecuencia, NivelEnergia, ImpactoEmocional, MotivoCancelacion
)
from backend.models.mock_data import MockPilar, MockMeta
from backend.logic.task_actions import (
    complete_task, send_to_inbox, delete_task,
    log_cancellation, reschedule_task, acknowledge_and_keep
)

tasks_bp = Blueprint("tasks", __name__)


# ─── LECTURA ──────────────────────────────────────────────────────────────────

@tasks_bp.route("/inbox", methods=["GET"])
def get_inbox():
    """
    Tareas en estado 'inbox' para el Gestor/Procesador Nocturno.
    Ordenadas por fecha de creación (más antiguas primero).
    """
    tasks = Task.query.filter_by(
        estado=TaskEstado.INBOX
    ).order_by(Task.fecha_creacion.asc()).all()

    return jsonify({
        "count": len(tasks),
        "tasks": [t.to_dict() for t in tasks]
    })


@tasks_bp.route("/", methods=["GET"])
def get_all_tasks():
    """
    Todas las tareas con filtros opcionales via query params:
    ?estado=planificada
    ?tipo=Estratégica
    ?contexto=Casa
    ?pilar_id=<uuid>
    """
    query = Task.query

    # Filtros opcionales
    if estado := request.args.get("estado"):
        try:
            query = query.filter_by(estado=TaskEstado(estado))
        except ValueError:
            return jsonify({"error": f"Estado inválido: {estado}"}), 400

    if tipo := request.args.get("tipo"):
        query = query.filter_by(tipo=TaskTipo(tipo))

    if contexto := request.args.get("contexto"):
        query = query.filter_by(contexto=TaskContexto(contexto))

    if pilar_id := request.args.get("pilar_id"):
        query = query.filter_by(pilar_id=pilar_id)

    # Excluir eliminadas por defecto
    if not request.args.get("include_deleted"):
        query = query.filter(Task.estado != TaskEstado.ELIMINADA)

    tasks = query.order_by(Task.fecha_creacion.desc()).all()
    return jsonify({"count": len(tasks), "tasks": [t.to_dict() for t in tasks]})


@tasks_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    """Detalle completo de una tarea."""
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict())


@tasks_bp.route("/selectors", methods=["GET"])
def get_selectors():
    """
    Datos para los selectores dinámicos del formulario de procesamiento.
    Retorna pilares, metas y todos los enums disponibles.
    """
    return jsonify({
        "pilares":    [p.to_dict() for p in MockPilar.query.all()],
        "metas":      [m.to_dict() for m in MockMeta.query.all()],
        "tipos":      [e.value for e in TaskTipo],
        "duraciones": [e.value for e in TaskDuracion],
        "contextos":  [e.value for e in TaskContexto],
        "frecuencias":[e.value for e in TaskFrecuencia],
        "energias":   [e.value for e in NivelEnergia],
        "impactos":   [e.value for e in ImpactoEmocional],
    })


# ─── CREACIÓN ─────────────────────────────────────────────────────────────────

@tasks_bp.route("/", methods=["POST"])
def create_task():
    """
    Crear tarea nueva.

    Captura rápida (FAB): solo requiere 'titulo'.
    La tarea se guarda en estado 'inbox' automáticamente.

    Procesamiento nocturno: puede incluir todos los campos enriquecidos.
    """
    data = request.get_json()

    if not data or not data.get("titulo"):
        return jsonify({"error": "El campo 'titulo' es obligatorio."}), 400

    titulo = data["titulo"].strip()
    if not titulo:
        return jsonify({"error": "El título no puede estar vacío."}), 400

    task = Task(titulo=titulo)

    # Campos opcionales (procesamiento nocturno)
    _update_task_fields(task, data)

    # Si se provee fecha_planificada, cambiar estado a planificada
    if task.fecha_planificada:
        task.estado = TaskEstado.PLANIFICADA

    # Validación de negocio: evento con hora requiere hora_inicio
    if task.es_evento_con_hora and not task.hora_inicio:
        return jsonify({"error": "Los eventos con hora requieren 'hora_inicio'."}), 400

    db.session.add(task)
    db.session.commit()

    return jsonify({
        "success": True,
        "task":    task.to_dict(),
        "message": f"Tarea '{task.titulo}' creada."
    }), 201


# ─── ACTUALIZACIÓN ────────────────────────────────────────────────────────────

@tasks_bp.route("/<task_id>", methods=["PUT"])
def update_task(task_id):
    """
    Editar tarea completa desde el Task Manager.
    Usado en el procesamiento nocturno para enriquecer una tarea del inbox.
    """
    task = Task.query.get_or_404(task_id)
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibieron datos."}), 400

    # Validar título si se incluye
    if "titulo" in data:
        titulo = data["titulo"].strip()
        if not titulo:
            return jsonify({"error": "El título no puede estar vacío."}), 400
        task.titulo = titulo

    _update_task_fields(task, data)

    # Si ahora tiene fecha_planificada, cambiar estado
    if task.fecha_planificada and task.estado == TaskEstado.INBOX:
        task.estado = TaskEstado.PLANIFICADA

    # Validación evento
    if task.es_evento_con_hora and not task.hora_inicio:
        return jsonify({"error": "Los eventos con hora requieren 'hora_inicio'."}), 400

    db.session.commit()
    return jsonify({"success": True, "task": task.to_dict()})


# ─── ELIMINACIÓN ─────────────────────────────────────────────────────────────

@tasks_bp.route("/<task_id>", methods=["DELETE"])
def delete_task_route(task_id):
    """Soft delete de tarea."""
    try:
        result = delete_task(task_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ─── ACCIONES RÁPIDAS (Dashboard) ─────────────────────────────────────────────

@tasks_bp.route("/<task_id>/complete", methods=["POST"])
def complete_task_route(task_id):
    """✅ Acción A: Marcar como completada."""
    try:
        result = complete_task(task_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@tasks_bp.route("/<task_id>/inbox", methods=["POST"])
def send_to_inbox_route(task_id):
    """📥 Acción B: Devolver al inbox para replanificar."""
    try:
        result = send_to_inbox(task_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
def cancel_task_route(task_id):
    """
    📨 Acción: Avisar/Cancelar evento en Modo Protección.
    Requiere el checkin_id activo para la correlación de datos.
    """
    data = request.get_json() or {}
    checkin_id = data.get("checkin_id")

    if not checkin_id:
        return jsonify({"error": "Se requiere 'checkin_id' para registrar la cancelación."}), 400

    motivo_str = data.get("motivo", "Salud/Energía")
    try:
        motivo = MotivoCancelacion(motivo_str)
    except ValueError:
        motivo = MotivoCancelacion.SALUD_ENERGIA

    try:
        result = log_cancellation(task_id, checkin_id, motivo)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@tasks_bp.route("/<task_id>/reschedule", methods=["POST"])
def reschedule_task_route(task_id):
    """📅 Acción: Reprogramar a nueva fecha."""
    data = request.get_json() or {}
    nueva_fecha = data.get("fecha")

    if not nueva_fecha:
        return jsonify({"error": "Se requiere el campo 'fecha' (YYYY-MM-DD)."}), 400

    try:
        result = reschedule_task(task_id, nueva_fecha)
        return jsonify(result)
    except (ValueError, Exception) as e:
        return jsonify({"error": str(e)}), 400


@tasks_bp.route("/<task_id>/acknowledge", methods=["POST"])
def acknowledge_route(task_id):
    """💪 Acción: 'Igual voy' — mantener evento pese a baja energía."""
    try:
        result = acknowledge_and_keep(task_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ─── Helper privado ───────────────────────────────────────────────────────────

def _update_task_fields(task: Task, data: dict):
    """
    Actualiza los campos de una tarea desde un dict de datos.
    Aplica conversiones de tipo y validaciones de negocio.
    Reutilizable en create y update.
    """
    enum_fields = {
        "tipo":                    TaskTipo,
        "duracion":                TaskDuracion,
        "contexto":                TaskContexto,
        "frecuencia":              TaskFrecuencia,
        "nivel_energia_requerido": NivelEnergia,
        "impacto_emocional":       ImpactoEmocional,
    }

    for field, EnumClass in enum_fields.items():
        if field in data and data[field] is not None:
            try:
                setattr(task, field, EnumClass(data[field]))
            except ValueError:
                pass  # Ignorar valores inválidos silenciosamente

    # Campos booleanos
    for bool_field in ("is_urgent", "is_important", "es_evento_con_hora"):
        if bool_field in data:
            setattr(task, bool_field, bool(data[bool_field]))

    # Fechas
    if "fecha_planificada" in data and data["fecha_planificada"]:
        task.fecha_planificada = date.fromisoformat(data["fecha_planificada"])

    # Hora de inicio (para eventos)
    if "hora_inicio" in data and data["hora_inicio"]:
        from datetime import time
        h, m = map(int, data["hora_inicio"].split(":"))
        task.hora_inicio = time(h, m)

    # Regla de recurrencia
    if "recurrence_rule" in data:
        task.recurrence_rule = data["recurrence_rule"]

    # Relaciones FK
    if "pilar_id" in data:
        task.pilar_id = data["pilar_id"]
    if "meta_id" in data:
        task.meta_id = data["meta_id"]

    # ── Regla de negocio: tipo condiciona relaciones ───────────────────────────
    # Si tipo == Cotidiana, limpiar meta_id
    # Si tipo == Estratégica, limpiar pilar_id
    if task.tipo == TaskTipo.COTIDIANA:
        task.meta_id = None
    elif task.tipo == TaskTipo.ESTRATEGICA:
        task.pilar_id = None

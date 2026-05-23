"""
MOSS - Lógica de Acciones sobre Tareas
Centraliza todas las operaciones que cambian el estado de una tarea.

Cada función es una "acción rápida" del Dashboard o del Task Manager.
"""

from datetime import datetime
from backend.app import db
from backend.models.task import Task, TaskEstado, MotivoCancelacion


def complete_task(task_id: str) -> dict:
    """
    Opción A del Dashboard: Marcar tarea como completada.
    Registra la fecha de completado para estadísticas futuras.
    """
    task = _get_task_or_raise(task_id)

    task.estado          = TaskEstado.COMPLETADA
    task.fecha_completado = datetime.utcnow()
    db.session.commit()

    return {
        "success":         True,
        "task_id":         task_id,
        "completed_at":    task.fecha_completado.isoformat(),
        "message":         f"✅ '{task.titulo}' completada."
    }


def send_to_inbox(task_id: str) -> dict:
    """
    Opción B del Dashboard: Devolver tarea al inbox para replanificar.
    Limpia la fecha_planificada y regresa al Gestor Nocturno.
    """
    task = _get_task_or_raise(task_id)

    task.estado            = TaskEstado.INBOX
    task.fecha_planificada = None   # Limpia la fecha → sale del Dashboard
    task.is_urgent         = False  # Resetea Eisenhower para re-evaluar
    task.is_important      = False
    db.session.commit()

    return {
        "success": True,
        "task_id": task_id,
        "message": f"📥 '{task.titulo}' devuelta al inbox para replanificar."
    }


def delete_task(task_id: str) -> dict:
    """
    Opción C del Dashboard: Soft delete de la tarea.
    Cambia estado a 'eliminada' sin borrar el registro de la DB.
    Preserva datos para estadísticas históricas.
    """
    task = _get_task_or_raise(task_id)

    task.estado = TaskEstado.ELIMINADA
    db.session.commit()

    return {
        "success": True,
        "task_id": task_id,
        "message": f"🗑️ '{task.titulo}' eliminada."
    }


def log_cancellation(
    task_id:    str,
    checkin_id: str,
    motivo:     MotivoCancelacion = MotivoCancelacion.SALUD_ENERGIA
) -> dict:
    """
    Acción especial para eventos en Modo Protección:
    "Avisar/Cancelar" → se ejecuta completamente en background.

    El usuario NO ve pasos adicionales ni confirmaciones.
    Todo el registro ocurre silenciosamente en un solo commit.

    Datos capturados para el futuro módulo de Análisis:
    - que fue cancelado por baja energía (fue_cancelado_por_energia)
    - cuándo ocurrió (fecha_cancelacion)
    - el motivo (motivo_cancelacion)
    - qué estado emocional tenía ese día (checkin_cancelacion_id → JOIN futuro)
    """
    task = _get_task_or_raise(task_id)

    # Todo en un solo commit — silencioso y rápido
    task.estado                   = TaskEstado.CANCELADA
    task.fue_cancelado_por_energia = True
    task.fecha_cancelacion        = datetime.utcnow()
    task.motivo_cancelacion       = motivo
    task.checkin_cancelacion_id   = checkin_id  # Contexto emocional del momento

    db.session.commit()

    return {
        "success":      True,
        "task_id":      task_id,
        "cancelled_at": task.fecha_cancelacion.isoformat(),
        "message":      f"📨 Registro de cancelación guardado para '{task.titulo}'."
        # El frontend solo usa esto para actualizar la UI
    }


def reschedule_task(task_id: str, nueva_fecha: str) -> dict:
    """
    Reprogramar un evento o tarea a una nueva fecha.
    Usado tanto en el Dashboard como en el Task Manager.
    """
    task = _get_task_or_raise(task_id)

    from datetime import date
    task.fecha_planificada = date.fromisoformat(nueva_fecha)
    task.estado            = TaskEstado.PLANIFICADA
    db.session.commit()

    return {
        "success":      True,
        "task_id":      task_id,
        "nueva_fecha":  nueva_fecha,
        "message":      f"📅 '{task.titulo}' reprogramada para {nueva_fecha}."
    }


def acknowledge_and_keep(task_id: str) -> dict:
    """
    Acción "💪 Igual voy" para eventos de alta energía en Modo Protección.
    El usuario reconoce que está cansado pero decide asistir de todas formas.
    No cambia el estado — solo registra el reconocimiento.
    """
    task = _get_task_or_raise(task_id)
    # El evento permanece PLANIFICADA — no se toca el estado.
    # En el futuro podríamos agregar un campo acknowledged=True
    # para métricas de "compromisos mantenidos bajo presión".

    return {
        "success": True,
        "task_id": task_id,
        "message": f"💪 Entendido. '{task.titulo}' permanece en tu agenda."
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_task_or_raise(task_id: str) -> Task:
    """Busca una tarea por ID o lanza un error claro."""
    task = Task.query.get(task_id)
    if not task:
        raise ValueError(f"Tarea '{task_id}' no encontrada.")
    return task

"""
MOSS - Lógica del Dashboard
El cerebro que filtra y organiza las tareas según el Check-in diario.

Esta lógica conecta:
  DailyCheckIn (mood + energía) → Modo del día → Filtrado de tareas → 3 Bloques
"""

from datetime import date, timedelta
from backend.models.task import Task, TaskEstado, NivelEnergia


def get_dashboard_data(checkin):
    """
    Función principal del Dashboard.
    Recibe el DailyCheckIn de hoy y retorna los 3 bloques de tareas
    organizados y filtrados, listos para el frontend.

    Args:
        checkin: Objeto DailyCheckIn del día actual.

    Returns:
        dict con estructura completa para renderizar el Dashboard.
    """
    today    = date.today()
    tomorrow = today + timedelta(days=1)
    mode     = checkin.dashboard_mode

    # ── Consultas base ─────────────────────────────────────────────────────────
    # Solo tareas activas (no eliminadas, no canceladas)
    estados_activos = [TaskEstado.PLANIFICADA]

    todas = Task.query.filter(
        Task.estado.in_(estados_activos)
    ).all()

    # ── Separar en bloques por fecha ───────────────────────────────────────────
    vencidas  = [t for t in todas if t.fecha_planificada and t.fecha_planificada < today]
    de_hoy    = [t for t in todas if t.fecha_planificada == today]
    de_manana = [t for t in todas if t.fecha_planificada == tomorrow]

    # Ordenar "hoy" por prioridad Eisenhower (top → media → delegar → mantenimiento)
    de_hoy = sorted(de_hoy, key=lambda t: t.eisenhower_prioridad)

    # ── Aplicar filtros según modo del día ─────────────────────────────────────
    resultado = _apply_mode_filters(
        mode=mode,
        vencidas=vencidas,
        de_hoy=de_hoy,
        de_manana=de_manana
    )

    # ── Separar eventos de tareas en el bloque "hoy" ──────────────────────────
    # Los eventos van PRIMERO (hard landscapes), ordenados por hora
    eventos_hoy = sorted(
        [t for t in resultado["today"]["tasks"] if t.es_evento_con_hora],
        key=lambda t: t.hora_inicio or __import__("datetime").time(23, 59)
    )
    tareas_hoy = [t for t in resultado["today"]["tasks"] if not t.es_evento_con_hora]

    return {
        "mode":    mode,
        "checkin": checkin.to_dict(),
        "banner":  resultado["banner"],
        "blocks": {
            "overdue": {
                "tasks":     [t.to_dict() for t in resultado["overdue"]["tasks"]],
                "collapsed": resultado["overdue"]["collapsed"],
                "count":     len(resultado["overdue"]["tasks"])
            },
            "today": {
                "eventos":              [t.to_dict() for t in eventos_hoy],
                "tareas":               [t.to_dict() for t in tareas_hoy],
                "hidden_count":         resultado["today"]["hidden_count"],
                "hidden_tasks":         [t.to_dict() for t in resultado["today"].get("hidden_tasks", [])]
            },
            "tomorrow": {
                "tasks":    [t.to_dict() for t in de_manana],
                "readonly": True,
                "count":    len(de_manana)
            }
        }
    }


def _apply_mode_filters(mode, vencidas, de_hoy, de_manana):
    """
    Aplica los filtros correspondientes según el modo del día.

    REGLA CRÍTICA DE INMUNIDAD:
    Los eventos (es_evento_con_hora == True) NUNCA se ocultan,
    independientemente del modo o nivel de energía.
    """
    banner        = {"show": False, "message": ""}
    hidden_tasks  = []
    hidden_count  = 0
    overdue_collapsed = False

    if mode == "proteccion":
        # Filtrar tareas de hoy con alta energía (NO eventos)
        tareas_visibles = []
        for tarea in de_hoy:
            es_alta_energia = tarea.nivel_energia_requerido == NivelEnergia.ALTA

            # REGLA DE INMUNIDAD: eventos nunca se ocultan
            if tarea.es_evento_con_hora:
                tareas_visibles.append(tarea)
            elif es_alta_energia:
                hidden_tasks.append(tarea)  # Ocultar pero guardar referencia
            else:
                tareas_visibles.append(tarea)

        hidden_count   = len(hidden_tasks)
        de_hoy         = tareas_visibles
        overdue_collapsed = True  # Minimizar vencidas para no añadir estrés

        if hidden_count > 0:
            banner = {
                "show":    True,
                "type":    "protection",
                "message": f"Hemos ocultado {hidden_count} tarea(s) de alta energía hoy para proteger tu bienestar.",
                "cta":     "Ver tareas ocultas"
            }

    elif mode == "rendimiento":
        # Mostrar todo + sugerir tareas del inbox
        inbox_count = Task.query.filter_by(estado=TaskEstado.INBOX).count()
        if inbox_count > 0:
            banner = {
                "show":    True,
                "type":    "opportunity",
                "message": f"¡Estás en modo rendimiento! Tienes {inbox_count} tarea(s) en el inbox que puedes adelantar.",
                "cta":     "Ver sugerencias del inbox"
            }

    return {
        "overdue": {
            "tasks":     vencidas,
            "collapsed": overdue_collapsed
        },
        "today": {
            "tasks":        de_hoy,
            "hidden_count": hidden_count,
            "hidden_tasks": hidden_tasks
        },
        "banner": banner
    }


def get_event_quick_actions(event, dashboard_mode):
    """
    Retorna las acciones rápidas disponibles para un evento
    según el modo del día y su nivel de energía.

    En Modo Protección + evento de Alta Energía → acciones de contingencia.
    En cualquier otro caso → acciones estándar.
    """
    es_evento_exigente = (
        dashboard_mode == "proteccion" and
        event.get("nivel_energia_requerido") == "Alta"
    )

    if es_evento_exigente:
        return [
            {
                "id":     "notify_cancel",
                "icon":   "📨",
                "label":  "Avisar/Cancelar",
                "action": "logCancellation",
                "style":  "warning"
                # Futuro: abrirá borrador de email/mensaje
            },
            {
                "id":     "reschedule",
                "icon":   "📅",
                "label":  "Reprogramar",
                "action": "openReschedulePicker",
                "style":  "neutral"
            },
            {
                "id":     "commit",
                "icon":   "💪",
                "label":  "Igual voy",
                "action": "acknowledgeAndKeep",
                "style":  "primary"
            }
        ]

    # Acciones estándar para todos los demás casos
    return [
        {"id": "complete",   "icon": "✅", "label": "Completar",   "action": "markComplete", "style": "success"},
        {"id": "reschedule", "icon": "📅", "label": "Reprogramar", "action": "openReschedulePicker", "style": "neutral"},
        {"id": "delete",     "icon": "🗑️", "label": "Eliminar",    "action": "softDelete", "style": "danger"}
    ]

"""
MOSS - Hook de Gamificación para Tareas
Archivo nuevo: backend/logic/xp_hooks.py

Este módulo conecta el sistema de tareas (Módulo 1) con el
sistema RPG de pilares (Módulo 3).

Debe llamarse desde tasks.py (routes) cuando una tarea
cambia de estado a COMPLETADA.

Tabla de XP:
  Tarea Cotidiana completada      → +10 XP al Pilar
  Tarea Estratégica completada    → +25 XP al Pilar (y evalúa Objetivo)
  Objetivo completado             → +50 XP al Pilar
  Meta completada                 → +200 XP al Pilar

Integración en routes/tasks.py:
  En el endpoint POST /api/tasks/<id>/complete, después de cambiar estado:
    from backend.logic.xp_hooks import on_task_completed
    xp_result = on_task_completed(task)
    # Incluir xp_result en la respuesta JSON
"""

from backend.app import db


# ── Tabla de XP por tipo de acción ────────────────────────────────────────────
XP_CONFIG = {
    "tarea_cotidiana":   10,
    "tarea_estrategica": 25,
    "objetivo":          50,
    "meta":             200,
}


def on_task_completed(task) -> dict:
    """
    HOOK PRINCIPAL — Llamar cuando una Task cambia a estado COMPLETADA.

    Flujo:
      1. Detectar tipo de tarea (Cotidiana vs Estratégica)
      2. Otorgar XP al Pilar correspondiente
      3. Si es Estratégica: verificar progreso del Objetivo vinculado (futuro)
      4. Retornar dict con efectos para incluir en la respuesta API

    Args:
        task: Objeto Task de SQLAlchemy

    Returns:
        dict con xp_ganado, nivel_subio, mensaje_nivel, etc.
    """
    resultado = {
        "xp_ganado":    0,
        "nivel_subio":  False,
        "nivel_nuevo":  None,
        "pilar_nombre": None,
        "mensaje":      None,
    }

    # ── 1. Determinar fuente de XP ─────────────────────────────────────────────
    es_estrategica = (task.tipo and task.tipo.value == "Estratégica")
    xp_cantidad    = XP_CONFIG["tarea_estrategica"] if es_estrategica \
                     else XP_CONFIG["tarea_cotidiana"]

    # ── 2. Otorgar XP al Pilar ─────────────────────────────────────────────────
    pilar = None

    if es_estrategica and task.meta_id:
        # Tarea estratégica: XP va al pilar de la Meta
        # TODO: Importar Meta aquí cuando las tablas estén migradas
        # meta = Meta.query.get(task.meta_id)
        # if meta and meta.pilar:
        #     pilar = meta.pilar
        pass
    elif task.pilar_id:
        # Tarea cotidiana: XP va directamente al Pilar
        from backend.models.pilar import Pilar
        pilar = Pilar.query.get(task.pilar_id)

    if pilar:
        xp_result = pilar.otorgar_xp(
            xp_cantidad,
            fuente=f"{'tarea_estrategica' if es_estrategica else 'tarea_cotidiana'}:{task.id}"
        )
        resultado.update({
            "xp_ganado":    xp_result["xp_ganado"],
            "nivel_subio":  xp_result["subio_nivel"],
            "nivel_nuevo":  xp_result["nivel_nuevo"],
            "pilar_nombre": pilar.nombre,
        })

        if xp_result["subio_nivel"]:
            from backend.models.pilar import NOMBRE_NIVEL
            nombre_nivel = NOMBRE_NIVEL.get(xp_result["nivel_nuevo"], "")
            resultado["mensaje"] = (
                f"🎉 ¡{pilar.nombre} subió al Nivel {xp_result['nivel_nuevo']}: "
                f"{nombre_nivel}!"
            )

    # ── 3. Verificar Objetivo vinculado (Tarea Estratégica) ────────────────────
    # TODO Planificador Semanal: cuando Task tenga objetivo_id, evaluar aquí
    # if es_estrategica and task.objetivo_id:
    #     from backend.models.objetivo_v3 import Objetivo
    #     objetivo = Objetivo.query.get(task.objetivo_id)
    #     if objetivo:
    #         efectos_objetivo = objetivo.check_progreso()
    #         resultado["objetivo_efectos"] = efectos_objetivo

    return resultado


def on_habit_completed(task) -> dict:
    """
    HOOK FUTURO — Para hábitos completados (Motor de Hábitos, Módulo futuro).
    Los hábitos también otorgarán XP pero con multiplicador de racha.

    TODO Módulo Hábitos:
      - Racha de 7 días → XP * 1.5
      - Racha de 30 días → XP * 2.0
      - Racha rota → XP normal (sin penalización)
    """
    pass


def calcular_xp_total_semana(pilar_id: str) -> dict:
    """
    HOOK FUTURO — Resumen semanal de XP ganado en un Pilar.
    Usado en el Centro de Mando y el Planificador Semanal.

    TODO Módulo Estadísticas:
      SELECT SUM(xp) FROM xp_log
      WHERE pilar_id = ? AND fecha >= (hoy - 7 días)
    """
    pass
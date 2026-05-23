/**
 * MOSS — Check-in Modal
 * Gatekeeper del sistema: si no hay check-in hoy, bloquea el dashboard.
 */
const CheckinModal = (() => {
  let _selectedMood   = null;
  let _selectedEnergy = null;

  function show() {
    _selectedMood   = null;
    _selectedEnergy = null;
    document.querySelectorAll(".mood-option, .energy-opt")
            .forEach(el => el.classList.remove("selected"));
    document.getElementById("checkin-modal").style.display = "flex";
  }

  function hide() {
    document.getElementById("checkin-modal").style.display = "none";
  }

  function selectMood(el) {
    document.querySelectorAll(".mood-option").forEach(e => e.classList.remove("selected"));
    el.classList.add("selected");
    _selectedMood = el.dataset.mood;
    _updateConfirmBtn();
  }

  function selectEnergy(el) {
    document.querySelectorAll(".energy-opt").forEach(e => e.classList.remove("selected"));
    el.classList.add("selected");
    _selectedEnergy = el.dataset.energy;
    _updateConfirmBtn();
  }

  function _updateConfirmBtn() {
    const btn = document.getElementById("checkin-confirm-btn");
    if (_selectedMood && _selectedEnergy) {
      btn.disabled = false;
      btn.textContent = "Comenzar mi día →";
    } else {
      btn.disabled = true;
      btn.textContent = "Selecciona tu estado y energía";
    }
  }

  async function confirm() {
    if (!_selectedMood || !_selectedEnergy) return;

    const btn = document.getElementById("checkin-confirm-btn");
    btn.disabled = true;
    btn.textContent = "Guardando...";

    try {
      const res = await API.checkin.create(_selectedMood, _selectedEnergy);
      AppState.setCheckin(res.checkin);
      hide();
      UI.toast(res.message, "success");
      await Dashboard.load();
    } catch (err) {
      // Si ya existe check-in hoy (409), cargar igual
      if (err.message.includes("409") || err.message.toLowerCase().includes("existe")) {
        const today = await API.checkin.getToday();
        if (today.checkin) {
          AppState.setCheckin(today.checkin);
          hide();
          await Dashboard.load();
        }
      } else {
        UI.toast("Error al guardar: " + err.message, "error");
        btn.disabled = false;
        _updateConfirmBtn();
      }
    }
  }

  return { show, hide, selectMood, selectEnergy, confirm };
})();


/**
 * MOSS — Task Manager (Backstage)
 * Vista de procesamiento nocturno: inbox + formulario de enriquecimiento.
 */
const TaskManager = (() => {
  let _selectors = null;
  let _activeTab = "inbox";

  async function load() {
    switchView("tasks");
    await loadInbox();
  }

  async function loadInbox() {
    try {
      UI.showLoading("inbox-list");
      const res = await API.tasks.getInbox();
      renderInbox(res.tasks);

      // Cargar selectores la primera vez
      if (!_selectors) {
        _selectors = await API.tasks.getSelectors();
        AppState.set("selectors", _selectors);
      }
    } catch (err) {
      UI.showError("inbox-list", "No se pudo cargar el inbox.");
    }
  }

  function renderInbox(tasks) {
    const list = document.getElementById("inbox-list");
    const count = document.getElementById("inbox-count");
    if (count) count.textContent = tasks.length;

    if (!tasks.length) {
      list.innerHTML = `<div class="empty-state">
        <span>🎉 Inbox vacío — todo procesado</span>
      </div>`;
      return;
    }

    list.innerHTML = tasks.map(t => `
      <div class="inbox-row" id="inbox-${t.id}">
        <div class="inbox-row-icon">○</div>
        <div class="inbox-row-info">
          <span class="inbox-row-title">${t.titulo}</span>
          <span class="inbox-row-date">${formatRelativeDate(t.fecha_creacion)}</span>
        </div>
        <button class="inbox-process-btn" onclick="TaskManager.openProcessor('${t.id}', this)">
          Procesar →
        </button>
      </div>`).join("");
  }

  // ── Formulario de procesamiento nocturno (cascada de pasos) ───────────────
  async function openProcessor(taskId, btn) {
    // Cerrar cualquier procesador abierto previamente
    document.querySelectorAll(".task-processor").forEach(el => el.remove());

    const row = document.getElementById("inbox-" + taskId);
    if (!row) return;

    // Marcar la fila como activa
    document.querySelectorAll(".inbox-row").forEach(r => r.classList.remove("active"));
    row.classList.add("active");

    // Cambiar botón a estado de carga
    if (btn) { btn.textContent = "Cargando..."; btn.disabled = true; }

    // FIX 2: Garantizar que los selectores (pilares, metas, enums) estén cargados
    // ANTES de renderizar el formulario. Esto soluciona el selector vacío de Metas.
    if (!_selectors) {
      try {
        _selectors = await API.tasks.getSelectors();
        AppState.set("selectors", _selectors);
      } catch (err) {
        UI.toast("No se pudieron cargar los selectores del servidor.", "error");
        if (btn) { btn.textContent = "Procesar →"; btn.disabled = false; }
        return;
      }
    }

    // Obtener datos actuales de la tarea
    let task;
    try {
      const res = await API.tasks.getAll({ estado: "inbox" });
      task = res.tasks.find(t => t.id === taskId);
    } catch {
      if (btn) { btn.textContent = "Procesar →"; btn.disabled = false; }
      return;
    }

    if (btn) { btn.textContent = "Procesar →"; btn.disabled = false; }

    const processor = document.createElement("div");
    processor.className = "task-processor";
    processor.id = "processor-" + taskId;
    processor.dataset.taskId = taskId;
    processor.innerHTML = processorTemplate(task, _selectors);
    row.insertAdjacentElement("afterend", processor);

    // Scroll suave hacia el procesador
    setTimeout(() => processor.scrollIntoView({ behavior: "smooth", block: "nearest" }), 100);

    // Escuchar cambios de tipo para mostrar selector condicional
    processor.querySelectorAll('[name="tipo"]').forEach(radio => {
      radio.addEventListener("change", (e) => {
        toggleRelacionSelector(processor, e.target.value, _selectors);
      });
    });

    // Escuchar duración para la regla de los 3 minutos
    processor.querySelectorAll('[name="duracion"]').forEach(radio => {
      radio.addEventListener("change", (e) => {
        toggle3MinRule(processor, e.target.value);
      });
    });

    // Escuchar es_evento_con_hora
    processor.querySelector('[name="es_evento_con_hora"]')?.addEventListener("change", (e) => {
      processor.querySelector(".hora-field").style.display =
        e.target.checked ? "block" : "none";
    });
  }

  function processorTemplate(task, sel) {
    const pilares = (sel.pilares || []).map(p =>
      `<option value="${p.id}">${p.nombre}</option>`).join("");
    const metas = (sel.metas || []).map(m =>
      `<option value="${m.id}">${m.nombre}</option>`).join("");
    const contextos  = (sel.contextos  || []).map(c => `<option value="${c}">${c}</option>`).join("");
    const energias   = (sel.energias   || []).map(e => `<option value="${e}">${e}</option>`).join("");
    const frecuencias= (sel.frecuencias|| []).map(f => `<option value="${f}">${f}</option>`).join("");

    return `
    <div class="processor-card">
      <div class="processor-header">
        <span class="processor-title">📋 ${task.titulo}</span>
        <button class="processor-close" onclick="this.closest('.task-processor').remove()">×</button>
      </div>

      <div class="processor-body">

        <!-- PASO 1: Duración -->
        <div class="processor-step">
          <label class="step-label">⏱ Duración</label>
          <div class="btn-group">
            <label class="btn-option ${task.duracion === '<3min' ? 'selected' : ''}">
              <input type="radio" name="duracion" value="<3min" ${task.duracion === '<3min' ? 'checked' : ''}>
              &lt; 3 min
            </label>
            <label class="btn-option ${task.duracion === '>3min' ? 'selected' : ''}">
              <input type="radio" name="duracion" value=">3min" ${task.duracion === '>3min' ? 'checked' : ''}>
              &gt; 3 min
            </label>
          </div>
        </div>

        <!-- Regla de los 3 minutos (oculta hasta que seleccionen < 3min) -->
        <div class="three-min-rule" id="three-min-rule-${task.id}" style="display:none">
          <div class="three-min-card">
            <div class="three-min-title">⚡ Regla de los 3 minutos</div>
            <div class="three-min-sub">¡Hazlo ahora! — ¿Te atreves?</div>
            <div class="three-min-actions">
              <button class="btn-yes" onclick="TaskManager.doItNow('${task.id}')">✅ Sí, ya lo hice</button>
              <button class="btn-no"  onclick="TaskManager.backToInbox('${task.id}')">⏸ No, al inbox</button>
            </div>
          </div>
        </div>

        <!-- PASO 2: Tipo -->
        <div class="processor-step">
          <label class="step-label">🏷 Tipo de tarea</label>
          <div class="btn-group">
            <label class="btn-option">
              <input type="radio" name="tipo" value="Cotidiana">Cotidiana
            </label>
            <label class="btn-option">
              <input type="radio" name="tipo" value="Estratégica">Estratégica
            </label>
          </div>
        </div>

        <!-- PASO 3: Vinculación condicional (Pilar o Meta) -->
        <div class="processor-step" id="selector-pilar-${task.id}" style="display:none">
          <label class="step-label">⚖️ Pilar relacionado</label>
          <select name="pilar_id" class="moss-select">
            <option value="">Seleccionar pilar...</option>
            ${pilares}
          </select>
        </div>

        <div class="processor-step" id="selector-meta-${task.id}" style="display:none">
          <label class="step-label">🎯 Meta relacionada</label>
          <select name="meta_id" class="moss-select">
            <option value="">Seleccionar meta...</option>
            ${metas}
          </select>
        </div>

        <!-- PASO 4: Energía -->
        <div class="processor-step">
          <label class="step-label">🔋 Energía requerida</label>
          <select name="nivel_energia_requerido" class="moss-select">
            <option value="">Seleccionar...</option>
            ${energias}
          </select>
        </div>

        <!-- PASO 5: Contexto -->
        <div class="processor-step">
          <label class="step-label">📍 Contexto</label>
          <select name="contexto" class="moss-select">
            <option value="">Seleccionar...</option>
            ${contextos}
          </select>
        </div>

        <!-- PASO 6: Frecuencia -->
        <div class="processor-step">
          <label class="step-label">🔁 Frecuencia</label>
          <select name="frecuencia" class="moss-select">
            ${frecuencias}
          </select>
          <!-- TODO Motor de Recurrencia (Fase: Planificador Semanal):
               Cuando frecuencia != "Única", ejecutar proyectRecurrences(taskId, frecuencia)
               que calculará dinámicamente las instancias para los próximos 3 meses
               usando el patrón RRULE guardado en recurrence_rule.
               Ejemplo: FREQ=WEEKLY;BYDAY=MO genera cada lunes por 12 semanas.
               Las instancias NO se guardan en DB — se calculan en lectura. -->
        </div>

        <!-- PASO 7: Fecha planificada -->
        <div class="processor-step">
          <label class="step-label">📅 Fecha planificada</label>
          <input type="date" name="fecha_planificada" class="moss-input"
                 min="${new Date().toISOString().split('T')[0]}">
        </div>

        <!-- PASO 8: ¿Es evento con hora? -->
        <div class="processor-step">
          <label class="step-label checkbox-label">
            <input type="checkbox" name="es_evento_con_hora">
            Es un compromiso con hora fija (reunión, cita, etc.)
          </label>
        </div>

        <div class="processor-step hora-field" style="display:none">
          <label class="step-label">🕐 Hora de inicio</label>
          <input type="time" name="hora_inicio" class="moss-input">
        </div>

        <!-- PASO 9: Urgente / Importante (Eisenhower) -->
        <div class="processor-step">
          <label class="step-label">Matriz Eisenhower</label>
          <div class="checkbox-row">
            <label class="checkbox-label">
              <input type="checkbox" name="is_urgent"> Urgente
            </label>
            <label class="checkbox-label">
              <input type="checkbox" name="is_important"> Importante
            </label>
          </div>
        </div>

      </div><!-- end processor-body -->

      <div class="processor-footer">
        <button class="btn-ghost" onclick="this.closest('.task-processor').remove()">Cancelar</button>
        <button class="btn-primary" onclick="TaskManager.saveTask('${task.id}')">
          Planificar tarea →
        </button>
      </div>
    </div>`;
  }

  function toggleRelacionSelector(processor, tipo, sel) {
    const taskId = processor.dataset.taskId;
    const pilarEl = document.getElementById(`selector-pilar-${taskId}`);
    const metaEl  = document.getElementById(`selector-meta-${taskId}`);
    if (pilarEl) pilarEl.style.display = tipo === "Cotidiana"   ? "block" : "none";
    if (metaEl)  metaEl.style.display  = tipo === "Estratégica" ? "block" : "none";
  }

  function toggle3MinRule(processor, duracion) {
    const taskId = processor.dataset.taskId;
    const rule = document.getElementById(`three-min-rule-${taskId}`);
    const body = processor.querySelector(".processor-body");
    if (!rule) return;

    if (duracion === "<3min") {
      rule.style.display = "block";
      // Ocultar el resto del formulario — la única decisión es hacer o no hacer
      Array.from(body.querySelectorAll(".processor-step")).forEach(el => {
        el.style.display = "none";
      });
      rule.style.display = "block";
    } else {
      rule.style.display = "none";
      Array.from(body.querySelectorAll(".processor-step")).forEach(el => {
        el.style.display = "block";
      });
    }
  }

  async function saveTask(taskId) {
    const processor = document.getElementById("processor-" + taskId);
    if (!processor) return;

    const data = {};
    processor.querySelectorAll("[name]").forEach(el => {
      if (el.type === "checkbox") {
        data[el.name] = el.checked;
      } else if (el.type === "radio") {
        if (el.checked) data[el.name] = el.value;
      } else if (el.value) {
        data[el.name] = el.value;
      }
    });

    // ── Validaciones de negocio ────────────────────────────────────────────
    // FIX 2: Pilares y Metas son opcionales mientras esos módulos no existan.
    // Solo avisamos (warning) pero NO bloqueamos el guardado.
    // TODO Fase Rueda de la Vida: cambiar a validación obligatoria para Cotidiana.
    // TODO Fase 12 Semanas:       cambiar a validación obligatoria para Estratégica.
    if (data.tipo === "Cotidiana" && !data.pilar_id) {
      UI.toast("Recomendación: vincula esta tarea a un Pilar (puedes hacerlo más adelante).", "info");
    }
    if (data.tipo === "Estratégica" && !data.meta_id) {
      UI.toast("Recomendación: vincula esta tarea a una Meta cuando la definas.", "info");
    }

    // Este sí es obligatorio porque es inmediato y verificable
    if (data.es_evento_con_hora && !data.hora_inicio) {
      UI.toast("Los eventos con hora requieren una hora de inicio.", "warning");
      return;
    }

    const btn = processor.querySelector(".btn-primary");
    btn.disabled = true;
    btn.textContent = "Guardando...";

    try {
      await API.tasks.update(taskId, data);

      // ── FIX 1: NO redirigir al Dashboard ──────────────────────────────────
      // Al guardar, removemos la fila del inbox y el procesador,
      // pero permanecemos en la vista del Gestor de Tareas.
      // El usuario decide cuándo ir al Dashboard.
      const inboxRow = document.getElementById("inbox-" + taskId);

      // Animación de éxito en la fila antes de removerla
      if (inboxRow) {
        inboxRow.style.transition = "all 0.3s";
        inboxRow.style.background = "rgba(184,204,122,0.08)";
        inboxRow.style.borderColor = "rgba(184,204,122,0.3)";
        setTimeout(() => {
          inboxRow.remove();
          processor.remove();
        }, 400);
      } else {
        processor.remove();
      }

      UI.toast("✓ Tarea planificada — continúa con la siguiente.", "success");

      // Recargar el inbox en background para actualizar el contador
      // sin interrumpir el flujo del usuario
      setTimeout(() => loadInbox(), 500);

    } catch (err) {
      UI.toast("Error al guardar: " + err.message, "error");
      btn.disabled = false;
      btn.textContent = "Planificar tarea →";
    }
  }

  async function doItNow(taskId) {
    try {
      await API.tasks.complete(taskId);
      UI.toast("⚡ ¡Hecho! Regla de los 3 minutos cumplida.", "success");
      document.getElementById("inbox-" + taskId)?.remove();
      document.getElementById("processor-" + taskId)?.remove();
      await loadInbox();
    } catch (err) {
      UI.toast("Error: " + err.message, "error");
    }
  }

  async function backToInbox(taskId) {
    // La tarea ya está en inbox — solo cerrar el procesador
    document.getElementById("processor-" + taskId)?.remove();
    document.getElementById("inbox-" + taskId)?.classList.remove("active");
    UI.toast("Tarea devuelta al inbox.", "info");
  }

  function formatRelativeDate(isoString) {
    if (!isoString) return "";
    const diff = Date.now() - new Date(isoString).getTime();
    const mins  = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days  = Math.floor(diff / 86400000);
    if (mins < 1)   return "Ahora mismo";
    if (mins < 60)  return `Hace ${mins} min`;
    if (hours < 24) return `Hace ${hours} h`;
    if (days === 1) return "Ayer";
    return `Hace ${days} días`;
  }

  return { load, loadInbox, openProcessor, saveTask, doItNow, backToInbox };
})();


/**
 * MOSS — FAB (Botón de captura rápida)
 */
const FAB = (() => {
  async function capture() {
    const titulo = prompt("¿Qué tienes en mente?\n(Se guarda en el inbox)");
    if (!titulo?.trim()) return;

    try {
      await API.tasks.create({ titulo: titulo.trim() });
      UI.toast(`"${titulo.trim()}" guardado en el inbox ✓`, "success");
      // Si estamos en la vista de tareas, recargar el inbox
      if (AppState.get("activeView") === "tasks") {
        await TaskManager.loadInbox();
      }
    } catch (err) {
      UI.toast("No se pudo guardar: " + err.message, "error");
    }
  }

  return { capture };
})();
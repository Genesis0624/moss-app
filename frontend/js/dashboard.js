/**
 * MOSS — Dashboard (Frontstage)
 * Renderiza los 3 bloques de tiempo y gestiona las Quick Actions.
 * Se re-renderiza automáticamente cuando cambia el check-in.
 */

const Dashboard = (() => {

  // ── Cargar datos del backend ──────────────────────────────────────────────
  async function load() {
    try {
      UI.showLoading("dashboard-content");
      const res = await API.checkin.getDashboard();

      if (res.needs_checkin) {
        CheckinModal.show();
        return;
      }

      AppState.setDashboard(res.dashboard);
      render(res.dashboard);
    } catch (err) {
      UI.showError("dashboard-content", "No se pudo cargar el dashboard. ¿Está el servidor corriendo?");
    }
  }

  // ── Render principal ──────────────────────────────────────────────────────
  function render(data) {
    if (!data) return;
    const mode = data.mode;

    renderGreeting(data.checkin);
    renderBanner(data.banner, mode);
    renderOverdue(data.blocks.overdue, mode);
    renderToday(data.blocks.today, mode, data.checkin?.id);
    renderTomorrow(data.blocks.tomorrow);
  }

  function renderGreeting(checkin) {
    const h = new Date().getHours();
    const greet = h < 12 ? "Buenos días" : h < 18 ? "Buenas tardes" : "Buenas noches";
    document.getElementById("greeting-text").textContent = greet + " ✦";

    const days   = ["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"];
    const months = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio",
                    "Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
    const now = new Date();
    document.getElementById("date-line").textContent =
      `${days[now.getDay()]}, ${now.getDate()} de ${months[now.getMonth()]} · ${now.getFullYear()}`;

    if (checkin) {
      const moodEmoji = { "eufórica":"✨","feliz":"😊","poderosa":"💪","bien":"🌿",
                          "apagada":"🌧","cansada":"😴","estresada":"😤","enferma":"🤒" };
      document.getElementById("checkin-summary").innerHTML =
        `${moodEmoji[checkin.mood] || ""} <strong>${capitalize(checkin.mood)}</strong> · ${checkin.energia}`;
      document.getElementById("mood-dot").className =
        "mood-dot " + (AppState.isProteccion() ? "protection" : AppState.isRendimiento() ? "rendimiento" : "");
    }
  }

  function renderBanner(banner, mode) {
    const el = document.getElementById("mode-banner");
    if (!banner?.show) { el.style.display = "none"; return; }

    el.style.display = "flex";
    el.className = `mode-banner ${mode}`;
    el.querySelector(".banner-icon").textContent =
      mode === "rendimiento" ? "⚡" : mode === "proteccion" ? "💛" : "ℹ️";
    el.querySelector(".banner-text").textContent = banner.message;

    const cta = el.querySelector(".banner-cta");
    cta.textContent = banner.cta || "Ver más";
    cta.onclick = () => {
      if (mode === "rendimiento") TaskManager.load();
      else toggleHiddenTasks();
    };
  }

  function renderOverdue(block, mode) {
    const section = document.getElementById("overdue-section");
    const body    = document.getElementById("overdue-body");
    const count   = document.getElementById("overdue-count");

    if (!block.tasks.length) {
      section.style.display = "none";
      return;
    }

    section.style.display = "block";
    count.textContent = `${block.tasks.length} tarea${block.tasks.length > 1 ? "s" : ""}`;

    // En modo protección, las vencidas se colapsan para no añadir estrés
    if (block.collapsed) {
      body.classList.add("collapsed");
      document.getElementById("overdue-toggle")?.classList.add("collapsed");
    }

    body.innerHTML = block.tasks.map(t => taskCard(t, "overdue")).join("");
    attachTaskActions(body);
  }

  function renderToday(block, mode, checkinId) {
    const body = document.getElementById("today-body");
    body.innerHTML = "";
    body.dataset.checkinId = checkinId || "";

    // Eventos primero (hard landscapes)
    const eventosHtml = (block.eventos || []).map(e => eventCard(e, mode)).join("");

    // Separador solo si hay eventos Y tareas
    const sep = eventosHtml && block.tareas?.length
      ? `<div class="block-separator">
           <span>Tareas del día</span>
         </div>`
      : "";

    // Tareas filtradas (las de alta energía ya vienen filtradas del backend en modo protección)
    const tareasHtml = (block.tareas || []).map(t => taskCard(t, "today")).join("");

    // Tareas ocultas (solo en modo protección)
    const hiddenHtml = block.hidden_count > 0
      ? `<div class="hidden-tasks-reveal" id="hidden-reveal" onclick="Dashboard.toggleHiddenTasks()">
           <span class="hidden-icon">🙈</span>
           <span>${block.hidden_count} tarea${block.hidden_count > 1 ? "s" : ""} de alta energía oculta${block.hidden_count > 1 ? "s" : ""} hoy</span>
           <span class="reveal-cta">Ver de todas formas</span>
         </div>
         <div id="hidden-tasks-container"></div>`
      : "";

    body.innerHTML = eventosHtml + sep + tareasHtml + hiddenHtml;

    // Guardar las tareas ocultas en el DOM para revelarlas si el usuario quiere
    if (block.hidden_tasks?.length) {
      body.dataset.hiddenTasks = JSON.stringify(block.hidden_tasks);
    }

    if (!eventosHtml && !tareasHtml) {
      body.innerHTML += `<div class="empty-state">
        <span>Todo listo por hoy ✦</span>
      </div>`;
    }

    attachTaskActions(body);
  }

  function renderTomorrow(block) {
    const body  = document.getElementById("tomorrow-body");
    const count = document.getElementById("tomorrow-count");

    if (!block.tasks.length) {
      document.getElementById("tomorrow-section").style.display = "none";
      return;
    }

    count.textContent = `${block.tasks.length} tarea${block.tasks.length > 1 ? "s" : ""}`;
    body.innerHTML = block.tasks.map(t => `
      <div class="tomorrow-card">
        <span class="tomorrow-icon">◌</span>
        <span class="tomorrow-title">${t.titulo}</span>
        <div class="tomorrow-tags">
          ${t.nivel_energia_requerido ? `<span class="tag tag-energy ${t.nivel_energia_requerido.toLowerCase()}">${t.nivel_energia_requerido}</span>` : ""}
          ${t.contexto ? `<span class="tag tag-context">${t.contexto}</span>` : ""}
        </div>
      </div>`).join("");
  }

  // ── Templates de tarjetas ─────────────────────────────────────────────────
  function taskCard(task, block) {
    const priorityClass = {
      top: "priority-top", media: "priority-media",
      delegar: "priority-delegar", mantenimiento: "priority-mant"
    }[task.eisenhower_label] || "priority-mant";

    const energyClass = { Alta: "high", Media: "med", Baja: "low" }[task.nivel_energia_requerido] || "";

    return `
    <div class="task-card" id="card-${task.id}" data-id="${task.id}">
      <div class="priority-indicator ${priorityClass}"></div>
      <div class="task-info">
        <div class="task-title">
          ${task.titulo}
          ${task.eisenhower_label === "top" ? '<span class="badge badge-top">Top</span>' : ""}
        </div>
        <div class="task-tags">
          ${task.pilar_nombre  ? `<span class="tag tag-pilar">${task.pilar_nombre}</span>` : ""}
          ${task.nivel_energia_requerido ? `<span class="tag tag-energy ${energyClass}">${task.nivel_energia_requerido}</span>` : ""}
          ${task.contexto      ? `<span class="tag tag-context">${task.contexto}</span>` : ""}
          ${task.es_evento_con_hora ? '<span class="tag tag-event">Evento</span>' : ""}
        </div>
      </div>
      <div class="task-actions">
        <button class="action-btn complete" data-action="complete" data-id="${task.id}" title="Completar">✓</button>
        <button class="action-btn inbox"    data-action="inbox"    data-id="${task.id}" title="Al inbox">↩</button>
        <button class="action-btn delete"   data-action="delete"   data-id="${task.id}" title="Eliminar">×</button>
      </div>
    </div>`;
  }

  function eventCard(event, mode) {
    const isHighEnergy  = event.nivel_energia_requerido === "Alta";
    const isAlert       = mode === "proteccion" && isHighEnergy;
    const checkinId     = document.getElementById("today-body")?.dataset.checkinId || "";

    return `
    <div class="event-strip ${isAlert ? "alert-high" : ""}" id="card-${event.id}" data-id="${event.id}">
      <div class="event-time">${event.hora_inicio || "–"}</div>
      ${isAlert ? '<span class="event-alert">⚠️</span>' : '<span class="event-icon">📅</span>'}
      <div class="event-info">
        <span class="event-title">${event.titulo}</span>
        ${isAlert ? '<span class="event-warning-text">Sabemos que hoy no es tu mejor día para esto</span>' : ""}
      </div>
      <div class="event-actions">
        ${isAlert ? `
          <button class="action-btn warn"     data-action="cancel"      data-id="${event.id}" data-checkin="${checkinId}" title="Avisar/Cancelar">📨</button>
          <button class="action-btn reschedule" data-action="reschedule" data-id="${event.id}" title="Reprogramar">📅</button>
          <button class="action-btn commit"   data-action="acknowledge" data-id="${event.id}" title="Igual voy">💪</button>
        ` : `
          <button class="action-btn complete" data-action="complete"    data-id="${event.id}" title="Completar">✓</button>
          <button class="action-btn reschedule" data-action="reschedule" data-id="${event.id}" title="Reprogramar">📅</button>
        `}
      </div>
    </div>`;
  }

  // ── Quick Actions (delegación de eventos) ─────────────────────────────────
  function attachTaskActions(container) {
    container.addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;

      const action    = btn.dataset.action;
      const id        = btn.dataset.id;
      const checkinId = btn.dataset.checkin || AppState.get("checkin")?.id;

      btn.disabled = true; // Evitar doble clic

      try {
        switch (action) {
          case "complete":
            await API.tasks.complete(id);
            animateRemove(id);
            break;

          case "inbox":
            await API.tasks.sendToInbox(id);
            animateRemove(id, "left");
            break;

          case "delete":
            if (confirm("¿Eliminar esta tarea?")) {
              await API.tasks.delete(id);
              animateRemove(id, "down");
            }
            break;

          case "cancel":
            await API.tasks.cancel(id, checkinId);
            markEventCancelled(id);
            break;

          case "reschedule":
            const fecha = prompt("Nueva fecha (YYYY-MM-DD):");
            if (fecha) {
              await API.tasks.reschedule(id, fecha);
              animateRemove(id);
            }
            break;

          case "acknowledge":
            await API.tasks.acknowledge(id);
            // Quitar el estado de alerta visualmente
            const card = document.getElementById("card-" + id);
            if (card) {
              card.classList.remove("alert-high");
              card.querySelector(".event-warning-text")?.remove();
            }
            break;
        }
      } catch (err) {
        UI.toast("Error: " + err.message, "error");
        btn.disabled = false;
      }
    });
  }

  // ── Animaciones de salida ─────────────────────────────────────────────────
  function animateRemove(id, direction = "right") {
    const card = document.getElementById("card-" + id);
    if (!card) return;
    const transforms = { right: "translateX(30px)", left: "translateX(-30px)", down: "translateY(10px)" };
    card.style.transition = "opacity 0.25s, transform 0.25s, max-height 0.3s 0.15s";
    card.style.opacity    = "0";
    card.style.transform  = transforms[direction];
    card.style.maxHeight  = card.offsetHeight + "px";
    setTimeout(() => {
      card.style.maxHeight = "0";
      card.style.padding   = "0";
      card.style.margin    = "0";
    }, 200);
    setTimeout(() => card.remove(), 450);
  }

  function markEventCancelled(id) {
    const card = document.getElementById("card-" + id);
    if (!card) return;
    card.style.opacity = "0.4";
    card.querySelector(".event-title").style.textDecoration = "line-through";
    card.querySelector(".event-actions").innerHTML =
      '<span style="font-size:11px;color:var(--moss-amber);padding:4px 8px">Cancelado · registrado</span>';
  }

  // ── Mostrar/ocultar tareas de alta energía ────────────────────────────────
  function toggleHiddenTasks() {
    const container = document.getElementById("hidden-tasks-container");
    const reveal    = document.getElementById("hidden-reveal");
    const body      = document.getElementById("today-body");
    const hidden    = JSON.parse(body.dataset.hiddenTasks || "[]");
    const isVisible = AppState.get("hiddenTasksVisible");

    if (!isVisible) {
      container.innerHTML = hidden.map(t => taskCard(t, "today")).join("");
      attachTaskActions(container);
      reveal.querySelector(".reveal-cta").textContent = "Ocultar de nuevo";
      AppState.set("hiddenTasksVisible", true);
    } else {
      container.innerHTML = "";
      reveal.querySelector(".reveal-cta").textContent = "Ver de todas formas";
      AppState.set("hiddenTasksVisible", false);
    }
  }

  // ── Toggle bloques colapsables ────────────────────────────────────────────
  function toggleBlock(name) {
    const body = document.getElementById(name + "-body");
    const btn  = document.getElementById(name + "-toggle");
    body.classList.toggle("collapsed");
    btn?.classList.toggle("collapsed");
  }

  function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : "";
  }

  return { load, render, toggleBlock, toggleHiddenTasks };
})();
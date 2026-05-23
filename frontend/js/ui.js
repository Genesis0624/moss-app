/**
 * MOSS — UI Utilities
 * Toast notifications, loading states, error states, view switcher.
 */

const UI = (() => {

  // ── Toast Notifications ───────────────────────────────────────────────────
  function toast(message, type = "info") {
    const colors = {
      success: "var(--moss-accent)",
      error:   "var(--moss-red)",
      warning: "var(--moss-amber)",
      info:    "var(--moss-blue)"
    };

    const t = document.createElement("div");
    t.className = "moss-toast";
    t.textContent = message;
    t.style.cssText = `
      position: fixed; bottom: 80px; right: 24px; z-index: 9999;
      background: var(--moss-card);
      border: 0.5px solid ${colors[type] || colors.info};
      color: var(--moss-text);
      padding: 10px 16px; border-radius: 8px;
      font-size: 13px; font-family: var(--font-body);
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
      opacity: 0; transform: translateY(10px);
      transition: all 0.2s;
      max-width: 320px; line-height: 1.4;
    `;
    document.body.appendChild(t);
    requestAnimationFrame(() => {
      t.style.opacity   = "1";
      t.style.transform = "translateY(0)";
    });
    setTimeout(() => {
      t.style.opacity   = "0";
      t.style.transform = "translateY(10px)";
      setTimeout(() => t.remove(), 200);
    }, 3000);
  }

  // ── Loading State ─────────────────────────────────────────────────────────
  function showLoading(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
      <div class="loading-state">
        <div class="loading-spinner"></div>
        <span>Cargando...</span>
      </div>`;
  }

  // ── Error State ───────────────────────────────────────────────────────────
  function showError(containerId, message) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
      <div class="error-state">
        <span>⚠️ ${message}</span>
        <button onclick="location.reload()" class="btn-ghost" style="margin-top:8px">Reintentar</button>
      </div>`;
  }

  // ── View Switcher ─────────────────────────────────────────────────────────
  function switchView(viewName) {
    // Actualizar estado global
    AppState.set("activeView", viewName);

    // Mostrar/ocultar vistas
    document.getElementById("dashboard-view")
      ?.classList.toggle("hidden", viewName !== "dashboard");
    document.getElementById("tasks-view")
      ?.classList.toggle("visible", viewName === "tasks");

    // Actualizar navegación sidebar
    document.querySelectorAll(".nav-btn[data-view]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.view === viewName);
    });

    // Actualizar FAB title
    const fab = document.getElementById("fab-btn");
    if (fab) fab.title = viewName === "tasks" ? "Nueva tarea rápida" : "Captura rápida";
  }

  return { toast, showLoading, showError, switchView };
})();

// Exponer switchView globalmente para los onclick del HTML
function switchView(view) { UI.switchView(view); }
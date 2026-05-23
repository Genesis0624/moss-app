/**
 * MOSS — Estado Global (AppState)
 * Fuente única de verdad para toda la aplicación.
 * Cuando cambia el check-in, el Dashboard se re-renderiza automáticamente.
 */

const AppState = (() => {
  let _state = {
    // Check-in del día
    checkin:       null,   // { id, fecha, mood, energia, dashboard_mode, mensaje_bienvenida }
    dashboardMode: "normal", // "rendimiento" | "normal" | "proteccion"

    // Datos del dashboard
    dashboard: null,       // respuesta completa del endpoint /checkin/dashboard

    // Selectores (pilares y metas mock)
    selectors: null,       // { pilares, metas, tipos, contextos, ... }

    // Vista activa
    activeView: "dashboard", // "dashboard" | "tasks"

    // UI state
    overdueCollapsed:  false,
    tomorrowCollapsed: false,
    hiddenTasksVisible: false,
  };

  // Suscriptores: funciones que se llaman cuando cambia el estado
  const _listeners = {};

  function on(event, fn) {
    if (!_listeners[event]) _listeners[event] = [];
    _listeners[event].push(fn);
  }

  function emit(event, data) {
    (_listeners[event] || []).forEach(fn => fn(data));
  }

  return {
    on,

    get: (key) => _state[key],

    set(key, value) {
      _state[key] = value;
      emit("change", { key, value });
      emit(`change:${key}`, value);
    },

    setCheckin(checkin) {
      _state.checkin       = checkin;
      _state.dashboardMode = checkin?.dashboard_mode || "normal";
      emit("change:checkin", checkin);
      emit("change:dashboardMode", _state.dashboardMode);
    },

    setDashboard(data) {
      _state.dashboard = data;
      emit("change:dashboard", data);
    },

    getMode() {
      return _state.dashboardMode;
    },

    isRendimiento() { return _state.dashboardMode === "rendimiento"; },
    isProteccion()  { return _state.dashboardMode === "proteccion"; },
  };
})();
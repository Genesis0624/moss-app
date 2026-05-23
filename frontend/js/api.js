/**
 * MOSS — API Client
 * Centraliza todas las llamadas al backend Flask.
 * Base URL apunta a localhost:5000 en desarrollo.
 */

const API = (() => {
  const BASE = "http://127.0.0.1:5000/api";

  async function request(method, endpoint, body = null) {
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body) options.body = JSON.stringify(body);

    try {
      const res = await fetch(BASE + endpoint, options);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
      return data;
    } catch (err) {
      console.error(`[MOSS API] ${method} ${endpoint}`, err.message);
      throw err;
    }
  }

  return {
    // ── Check-in ────────────────────────────────────────────────────────────
    checkin: {
      getToday:      ()           => request("GET",  "/checkin/today"),
      create:        (mood, energia) => request("POST", "/checkin/",    { mood, energia }),
      getDashboard:  ()           => request("GET",  "/checkin/dashboard"),
    },

    // ── Tareas ──────────────────────────────────────────────────────────────
    tasks: {
      getInbox:      ()           => request("GET",  "/tasks/inbox"),
      getAll:        (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request("GET", `/tasks/${qs ? "?" + qs : ""}`);
      },
      getSelectors:  ()           => request("GET",  "/tasks/selectors"),
      create:        (data)       => request("POST", "/tasks/",         data),
      update:        (id, data)   => request("PUT",  `/tasks/${id}`,    data),
      delete:        (id)         => request("DELETE",`/tasks/${id}`),

      // Acciones rápidas del Dashboard
      complete:      (id)         => request("POST", `/tasks/${id}/complete`),
      sendToInbox:   (id)         => request("POST", `/tasks/${id}/inbox`),
      cancel:        (id, checkinId) => request("POST", `/tasks/${id}/cancel`, {
        checkin_id: checkinId,
        motivo: "Salud/Energía"
      }),
      reschedule:    (id, fecha)  => request("POST", `/tasks/${id}/reschedule`, { fecha }),
      acknowledge:   (id)         => request("POST", `/tasks/${id}/acknowledge`),
    },
  };
})();
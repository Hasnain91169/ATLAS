const storageKeys = {
  url: "atlasServerUrl",
  token: "atlasToken",
  remember: "atlasRememberToken",
};

const el = (id) => document.getElementById(id);

const state = {
  url: "",
  token: "",
  refreshMs: 45000,
  timer: null,
};

const setStatus = (text) => {
  el("statusLine").textContent = text;
};

const loadSettings = () => {
  state.url = localStorage.getItem(storageKeys.url) || "";
  const remember = localStorage.getItem(storageKeys.remember) === "true";
  state.token = remember
    ? localStorage.getItem(storageKeys.token) || ""
    : sessionStorage.getItem(storageKeys.token) || "";
  el("serverUrl").value = state.url;
  el("token").value = state.token;
  el("rememberToken").checked = remember;
};

const saveSettings = () => {
  state.url = el("serverUrl").value.trim();
  state.token = el("token").value.trim();
  const remember = el("rememberToken").checked;
  localStorage.setItem(storageKeys.url, state.url);
  localStorage.setItem(storageKeys.remember, remember ? "true" : "false");
  sessionStorage.setItem(storageKeys.token, state.token);
  if (remember) {
    localStorage.setItem(storageKeys.token, state.token);
  } else {
    localStorage.removeItem(storageKeys.token);
  }
  setStatus("Settings saved.");
};

const fetchJson = async (path) => {
  if (!state.url) {
    throw new Error("Server URL is required.");
  }
  const response = await fetch(`${state.url}${path}`, {
    headers: {
      "X-ATLAS-TOKEN": state.token,
    },
  });
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}).`);
  }
  return response.json();
};

const refresh = async () => {
  try {
    const [brief, board, hourly, alerts, tasks] = await Promise.all([
      fetchJson("/api/v1/latest/daily-brief"),
      fetchJson("/api/v1/latest/board-report"),
      fetchJson("/api/v1/latest/hourly-plan"),
      fetchJson("/api/v1/alerts?limit=20"),
      fetchJson("/api/v1/tasks?status=needsAction&limit=10"),
    ]);
    el("dailyBrief").textContent = brief.data ? brief.data.markdown : "No data yet.";
    el("boardReport").textContent = board.data ? board.data.raw_markdown : "No data yet.";
    el("hourlyPlan").textContent = hourly.data ? hourly.data.raw_markdown : "No data yet.";
    el("alerts").textContent =
      alerts.alerts && alerts.alerts.length
        ? alerts.alerts
            .map((alert) => `[${alert.severity}] ${alert.title}\n${alert.message_markdown}`)
            .join("\n\n")
        : "No data yet.";
    el("tasks").textContent =
      tasks.tasks && tasks.tasks.length
        ? tasks.tasks
            .map((task) => `${task.title} (${task.status}, due: ${task.due || "No due date"})`)
            .join("\n")
        : "No data yet.";
    setStatus(`Last refreshed at ${new Date().toLocaleTimeString()}.`);
  } catch (err) {
    setStatus(err.message);
  }
};

const scheduleRefresh = () => {
  if (state.timer) {
    clearInterval(state.timer);
  }
  state.timer = setInterval(refresh, state.refreshMs);
};

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  el("saveBtn").addEventListener("click", () => {
    saveSettings();
    refresh();
    scheduleRefresh();
  });
  el("refreshBtn").addEventListener("click", () => {
    refresh();
  });
  if (state.url && state.token) {
    refresh();
    scheduleRefresh();
  }
});

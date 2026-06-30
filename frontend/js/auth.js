const API = "";  // same origin — no base URL needed
const ADMIN_EMAIL_SUFFIX = "@smartbank.admin";

function saveTokens(access, refresh) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function getToken() {
  return localStorage.getItem("access_token");
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    return null;
  }
}

function isAdminUser(user) {
  return Boolean(user?.email?.toLowerCase().endsWith(ADMIN_EMAIL_SUFFIX));
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "/app/login.html";
  }
}

function requireAdmin() {
  if (!getToken()) {
    window.location.href = "/app/login.html";
    return;
  }
  const user = getStoredUser();
  if (user && !isAdminUser(user)) {
    window.location.href = "/app/dashboard.html";
  }
}

function postLoginRedirect(user) {
  if (isAdminUser(user)) {
    window.location.href = "/app/admin.html";
  } else {
    window.location.href = "/app/dashboard.html";
  }
}

function parseJsonResponse(xhr) {
  try {
    return JSON.parse(xhr?.responseText || "{}");
  } catch {
    return {};
  }
}

function formatApiError(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((e) => e.msg || JSON.stringify(e)).join("; ");
  }
  return data.message || fallback;
}

function handleAdminApiError(xhr, fallback) {
  if (!xhr) return fallback;
  if (xhr.status === 401) {
    clearTokens();
    window.location.href = "/app/login.html";
    return "Session expired. Please sign in again.";
  }
  if (xhr.status === 403) {
    return "You do not have permission to perform this action.";
  }
  return formatApiError(parseJsonResponse(xhr), fallback);
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(API + path, { ...options, headers });
  if (res.status === 401) {
    clearTokens();
    window.location.href = "/app/login.html";
    return;
  }
  return res;
}

async function downloadReceipt(reference) {
  const token = getToken();
  if (!token) {
    window.location.href = "/app/login.html";
    return;
  }
  const res = await fetch(
    `${API}/transfers/${encodeURIComponent(reference)}/receipt`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (res.status === 401) {
    clearTokens();
    window.location.href = "/app/login.html";
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(formatApiError(err, "Could not download receipt"));
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `SmartBank-Receipt-${reference}.html`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function logout() {
  const refresh = localStorage.getItem("refresh_token");
  if (refresh) {
    await apiFetch("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refresh }),
    });
  }
  clearTokens();
  window.location.href = "/app/login.html";
}

document.body?.addEventListener("htmx:configRequest", (event) => {
  const token = getToken();
  if (token) {
    event.detail.headers.Authorization = `Bearer ${token}`;
  }
});

document.body?.addEventListener("htmx:responseError", (event) => {
  const xhr = event.detail.xhr;
  if (xhr?.status === 401) {
    clearTokens();
    window.location.href = "/app/login.html";
  }
});

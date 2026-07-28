export const DIGITAL_TWIN_BASE_URL =
  process.env.NEXT_PUBLIC_DIGITAL_TWIN_BASE_URL ||
  "https://server-digitaltwin-enterprise-testing.up.railway.app";

export const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "digital_twin_token";
const USER_KEY = "digital_twin_user";
const COOKIE_SESSION_SENTINEL = "cookie-session";

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token || COOKIE_SESSION_SENTINEL);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated() {
  return !!getToken();
}

function authFetchOptions() {
  const token = getToken();
  if (!token) {
    throw new Error("Not authenticated. Please log in again.");
  }

  const options = { credentials: "include" };

  if (token !== COOKIE_SESSION_SENTINEL) {
    options.headers = { Authorization: `Bearer ${token}` };
  }

  return options;
}

export async function login(email, password) {
  const response = await fetch(`${DIGITAL_TWIN_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(`Login failed (status ${response.status}). Check your email and password.`);
  }

  const data = await response.json().catch(() => ({}));

  saveSession(data.access_token || null, data.user);
  return data.user;
}

async function fetchProcessById(id) {
  try {
    const response = await fetch(`${DIGITAL_TWIN_BASE_URL}/process/${id}`, {
      ...authFetchOptions(),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function fetchProcessesPage({ page = 1, limit = 100, search = "" } = {}) {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (search) params.set("search", search);

  const response = await fetch(`${DIGITAL_TWIN_BASE_URL}/process?${params.toString()}`, {
    ...authFetchOptions(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load processes (status ${response.status}).`);
  }

  return response.json();
}

export async function fetchAllProcesses({ search = "" } = {}) {
  const trimmed = search.trim();
  const pageSize = 100;
  const maxPages = 50;
  const isNumericId = /^\d+$/.test(trimmed);
  const idMatchPromise = isNumericId ? fetchProcessById(trimmed) : Promise.resolve(null);

  let all = [];
  let page = 1;
  while (page <= maxPages) {
    const result = await fetchProcessesPage({ page, limit: pageSize, search: trimmed });
    const data = result.data || [];
    all = all.concat(data);

    const totalPages = result.totalPages || 1;
    if (page >= totalPages || data.length === 0) break;
    page += 1;
  }

  const idMatch = await idMatchPromise;
  if (idMatch && !all.some((p) => p.process_id === idMatch.process_id)) {
    all = [idMatch, ...all];
  }

  return all;
}

export async function fetchProcessWithRelations(id) {
  const response = await fetch(`${DIGITAL_TWIN_BASE_URL}/process/${id}/with-relations`, {
    ...authFetchOptions(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load process ${id} (status ${response.status}).`);
  }

  return response.json();
}

export async function fetchProcessBundle(id) {
  const visited = new Set([id]);
  const subprocesses = {};

  const main = await fetchProcessWithRelations(id);

  async function collectChildren(processData) {
    const childIds = (processData.process_task || [])
      .map((pt) => pt.child_process_id)
      .filter((cid) => cid != null && !visited.has(cid));

    for (const cid of childIds) {
      visited.add(cid);
      const childData = await fetchProcessWithRelations(cid);
      subprocesses[cid] = childData;
      await collectChildren(childData);
    }
  }

  await collectChildren(main);

  return { process: main, subprocesses };
}

export async function runRedesign(bundle) {
  const response = await fetch(`${BACKEND_BASE_URL}/redesign/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bundle),
  });

  if (!response.ok) {
    throw new Error(`Redesign request failed (status ${response.status}).`);
  }

  return response.json();
}

// Digital Twin Server -- live API client (auth, process listing/fetching, bundling).
// Base URL defaults to the testing environment; override with
// NEXT_PUBLIC_DIGITAL_TWIN_BASE_URL for production.
export const DIGITAL_TWIN_BASE_URL =
  process.env.NEXT_PUBLIC_DIGITAL_TWIN_BASE_URL ||
  "https://server-digitaltwin-enterprise-testing.up.railway.app";

export const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "digital_twin_token";
const USER_KEY = "digital_twin_user";
// Sentinel stored when the server authenticates via an httpOnly cookie instead of
// returning a bearer token in the response body -- there is nothing readable to
// store in that case, this just marks "the last login call succeeded" for routing.
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

  // "credentials: include" makes the browser send the httpOnly auth cookie on every
  // cross-origin request to the Digital Twin API -- required whether or not we also
  // have a bearer token, since some deployments set the cookie regardless.
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
    credentials: "include", // allow the server to set an auth cookie in the response
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(`Login failed (status ${response.status}). Check your email and password.`);
  }

  const data = await response.json().catch(() => ({}));

  // The token may come back in the body (bearer-header auth) or not at all (the
  // server set it as an httpOnly cookie instead, which JS can't read) -- either way,
  // a 2xx response here means login succeeded.
  saveSession(data.access_token || null, data.user);
  return data.user;
}

export async function fetchProcesses({ page = 1, limit = 10, search = "" } = {}) {
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

export async function fetchProcessWithRelations(id) {
  const response = await fetch(`${DIGITAL_TWIN_BASE_URL}/process/${id}/with-relations`, {
    ...authFetchOptions(),
  });

  if (!response.ok) {
    throw new Error(`Failed to load process ${id} (status ${response.status}).`);
  }

  return response.json();
}

/**
 * Fetches a process plus every subprocess it references (recursively). Returns
 * {process, subprocesses} ready to POST to the backend's /redesign/process bundle
 * endpoint -- the backend never needs its own Digital Twin API credentials since
 * everything it needs is bundled here.
 *
 * Deliberately does NOT fetch bpmn_xml from the separate /bpmn-native/generate
 * endpoint -- that BPMN generator is still under construction on the server and is
 * sometimes slow, wrong, or simply unavailable for a given process. The backend
 * builds the process graph directly from process_task[]/gateways[] (the same data
 * fetched here) whenever bpmn_xml is missing or unusable, so skipping this call
 * removes an extra request and its failure mode entirely rather than working around it.
 */
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

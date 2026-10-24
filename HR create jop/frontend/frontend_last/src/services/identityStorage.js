// Minimal persistence for the development-only identity that the FastAPI
// backend expects via X-Organization-Id / X-User-Id headers.
//
// This is NOT authentication. It is a local development convenience:
// environment-configured defaults are used when nothing has been persisted,
// and a persisted identity overrides those defaults.

const STORAGE_KEY = "hera.devIdentity";

const ENV_DEFAULTS = {
  organizationId: import.meta.env.VITE_ORG_ID || "",
  userId: import.meta.env.VITE_USER_ID || "",
  organizationName: "",
  userName: "",
};

export function getEnvDefaultIdentity() {
  return { ...ENV_DEFAULTS };
}

export function getStoredIdentity() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return {
      organizationId: parsed.organizationId || "",
      userId: parsed.userId || "",
      organizationName: parsed.organizationName || "",
      userName: parsed.userName || "",
    };
  } catch {
    return null;
  }
}

export function saveIdentity(identity) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
}

export function clearIdentity() {
  localStorage.removeItem(STORAGE_KEY);
}
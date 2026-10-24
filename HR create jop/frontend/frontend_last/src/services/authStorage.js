/**
 * Session storage management for HERA authentication tokens.
 *
 * Security notes:
 * - Access token is kept in sessionStorage under a dedicated application key.
 * - Storing tokens in sessionStorage ensures they do not persist across browser
 *   sessions or leak into disk-backed localStorage.
 * - Never stores passwords, signing keys, or untrusted identity claims.
 */

const TOKEN_KEY = "hera.auth.token";
const LEGACY_DEV_IDENTITY_KEY = "hera.devIdentity";

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

export function setToken(token) {
  if (!token) return;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    // Ensure any legacy dev identity in localStorage is cleaned up
    localStorage.removeItem(LEGACY_DEV_IDENTITY_KEY);
  } catch {
    // sessionStorage write error (e.g. private browsing restrictions)
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_DEV_IDENTITY_KEY);
  } catch {
    // ignore cleanup errors
  }
}

export function hasToken() {
  return Boolean(getToken());
}

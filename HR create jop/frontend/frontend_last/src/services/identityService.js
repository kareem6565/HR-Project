import apiClient from "./apiClient";
import {
  getEnvDefaultIdentity,
  getStoredIdentity,
  saveIdentity,
  clearIdentity as clearStoredIdentity,
} from "./identityStorage";

// Development identity model. The IDs (organizationId / userId) are the
// authoritative values sent to the backend; names are display-only.

function effectiveIdentity() {
  const stored = getStoredIdentity();
  if (stored && (stored.organizationId || stored.userId)) return stored;
  return getEnvDefaultIdentity();
}

export function getIdentity() {
  const effective = effectiveIdentity();
  return {
    organizationId: effective.organizationId || "",
    userId: effective.userId || "",
    organizationName: effective.organizationName || "",
    userName: effective.userName || "",
  };
}

export function hasIdentity() {
  const identity = getIdentity();
  return Boolean(identity.organizationId && identity.userId);
}

export function setIdentity(patch) {
  const identity = { ...getIdentity(), ...patch };
  saveIdentity({
    organizationId: identity.organizationId || "",
    userId: identity.userId || "",
    organizationName: identity.organizationName || "",
    userName: identity.userName || "",
  });
  return getIdentity();
}

export function resetIdentity() {
  clearStoredIdentity();
  return getIdentity();
}

// Bootstrap support: unauthenticated endpoints that create a development
// organization and user so a valid identity can be obtained locally.

export async function createOrganization(name) {
  const { data } = await apiClient.post("/organizations", { name });
  return data;
}

export async function createUser(organizationId, { email, fullName }) {
  const { data } = await apiClient.post(`/organizations/${organizationId}/users`, {
    email,
    full_name: fullName,
  });
  return data;
}
import apiClient from "./apiClient";

export async function getGoogleConnectionStatus() {
  const { data } = await apiClient.get("/hr/google/status");
  return data;
}

export async function getGoogleConnectUrl() {
  const { data } = await apiClient.get("/hr/google/connect");
  return data;
}

export async function disconnectGoogleConnection() {
  const { data } = await apiClient.delete("/hr/google/disconnect");
  return data;
}

export async function processEmailOutbox() {
  const { data } = await apiClient.post("/hr/email-outbox/process");
  return data;
}

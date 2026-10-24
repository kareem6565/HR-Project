import apiClient from "./apiClient";

// AI-settings service. Contract: src/types/api/ai-settings.js.
//
// Backs the Settings page: shows which AI provider is active and lets the user
// add a Soal API key at runtime (used when the server's env key hits its
// free-tier rate limit) or clear it. The key is stored in memory on the server
// and is never returned to the client — only its presence/source is.

export async function getAISettings() {
  const { data } = await apiClient.get("/settings/ai");
  return data;
}

export async function setApiKey(apiKey) {
  const { data } = await apiClient.post("/settings/ai/api-key", { api_key: apiKey });
  return data;
}

export async function clearApiKey() {
  const { data } = await apiClient.delete("/settings/ai/api-key");
  return data;
}

export async function verifyApiKey(apiKey) {
  const body = apiKey ? { api_key: apiKey } : {};
  const { data } = await apiClient.post("/settings/ai/verify", body);
  return data;
}
import apiClient from "./apiClient";

// HERA chat service. Contract: backend/app/api/v1/schemas/chat.py.
// Threads and messages are org-scoped through the identity headers apiClient
// attaches (X-Organization-Id / X-User-Id). Sending a message runs the HERA
// assistant workflow (plan -> authorized tools -> compose) on the backend and
// persists both turns; the assistant message carries tool_calls / tool_results
// that ground the reply in real pipeline data.

function adaptThread(row) {
  return {
    id: row.id,
    title: row.title || null,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function adaptMessage(row) {
  return {
    id: row.id,
    threadId: row.chat_thread_id,
    role: row.role,
    content: row.content,
    toolCalls: row.tool_calls || [],
    toolResults: row.tool_results || [],
    workflowRunId: row.workflow_run_id || null,
    createdAt: row.created_at,
  };
}

export async function listThreads() {
  const { data } = await apiClient.get("/chat/threads");
  return (data.threads || []).map(adaptThread);
}

export async function createThread(title = null) {
  const { data } = await apiClient.post("/chat/threads", title ? { title } : {});
  return adaptThread(data);
}

export async function getThread(threadId) {
  const { data } = await apiClient.get(`/chat/threads/${threadId}`);
  return {
    thread: adaptThread(data.thread),
    messages: (data.messages || []).map(adaptMessage),
  };
}

export async function renameThread(threadId, title) {
  const { data } = await apiClient.patch(`/chat/threads/${threadId}`, { title });
  return adaptThread(data);
}

export async function sendMessage(threadId, content) {
  const { data } = await apiClient.post(`/chat/threads/${threadId}/messages`, {
    content,
  });
  return {
    thread: adaptThread(data.thread),
    message: adaptMessage(data.message),
  };
}
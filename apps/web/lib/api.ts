/**
 * Typed API client for the AI Agent Platform backend.
 * All requests attach the Supabase JWT from the session.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TaskStatus =
  | "pending" | "queued" | "in_progress"
  | "awaiting_approval" | "completed" | "failed" | "cancelled";

export interface Task {
  id: string;
  tenant_id: string;
  created_by: string;
  title: string;
  description: string;
  priority: "low" | "normal" | "high";
  status: TaskStatus;
  result: { output?: string } | null;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface TaskListResponse {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
}

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listTasks(
  token: string,
  page = 1,
  pageSize = 20
): Promise<APIResponse<TaskListResponse>> {
  return request(`/api/v1/tasks?page=${page}&page_size=${pageSize}`, token);
}

export async function createTask(
  token: string,
  payload: { title: string; description: string; priority?: string }
): Promise<APIResponse<Task>> {
  return request("/api/v1/tasks", token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTask(
  token: string,
  taskId: string
): Promise<APIResponse<Task>> {
  return request(`/api/v1/tasks/${taskId}`, token);
}

export async function cancelTask(
  token: string,
  taskId: string
): Promise<APIResponse<Task>> {
  return request(`/api/v1/tasks/${taskId}`, token, { method: "DELETE" });
}

export async function ingestDocument(
  token: string,
  payload: { document_id: string; title: string; content: string }
): Promise<{ document_id: string; chunks_indexed: number }> {
  const res = await request<APIResponse<{ document_id: string; chunks_indexed: number }>>(
    "/api/v1/documents/ingest",
    token,
    { method: "POST", body: JSON.stringify(payload) }
  );
  return res as unknown as { document_id: string; chunks_indexed: number };
}

export async function uploadDocument(
  token: string,
  file: File,
  title: string,
  documentId?: string,
): Promise<{ document_id: string; chunks_indexed: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  if (documentId) form.append("document_id", documentId);

  const res = await fetch(`${BASE}/api/v1/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

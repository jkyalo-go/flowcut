import { ApiError, api } from "@/lib/api";

interface UploadToProjectOptions {
  workspaceId: string;
  projectId: string;
  file: File;
}

async function putUploadBody(sessionId: string, file: File): Promise<void> {
  const response = await fetch(`/api/uploads/sessions/${sessionId}`, {
    method: "PUT",
    credentials: "include",
    body: file,
  });
  if (response.ok) return;

  let message = `HTTP ${response.status}`;
  try {
    const data = await response.json();
    message = data.detail ?? data.message ?? message;
  } catch {
    void 0;
  }
  throw new ApiError(response.status, message);
}

export async function uploadFileToProject({
  workspaceId,
  projectId,
  file,
}: UploadToProjectOptions): Promise<void> {
  const session = await api.post<{ id: string }>("/api/uploads/sessions", {
    workspace_id: workspaceId,
    project_id: projectId,
    filename: file.name,
    total_size: file.size,
    media_type: file.type,
  });

  await putUploadBody(session.id, file);
  await api.post(`/api/uploads/sessions/${session.id}/complete`, {
    project_id: projectId,
    total_size: file.size,
  });
}

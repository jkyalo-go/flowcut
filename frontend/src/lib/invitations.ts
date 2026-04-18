import { api } from "@/lib/api";
import type { User, Workspace } from "@/types";

const PENDING_INVITE_KEY = "flowcut_pending_invite_token";

export function rememberPendingInvite(token: string | null | undefined): void {
  if (typeof window === "undefined" || !token) return;
  sessionStorage.setItem(PENDING_INVITE_KEY, token);
}

export function getPendingInviteToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(PENDING_INVITE_KEY);
}

export function clearPendingInviteToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(PENDING_INVITE_KEY);
}

export interface InvitationSession {
  token: string;
  user: User;
  workspace: Workspace;
}

export async function completePendingInvite(): Promise<InvitationSession | null> {
  const token = getPendingInviteToken();
  if (!token) return null;
  const session = await api.post<InvitationSession>(`/invitations/${token}/accept`);
  clearPendingInviteToken();
  return session;
}

/** API skating session types (backend `/api/v1/sessions`). */

export interface SkateSession {
  id: string;
  user_id: string;
  spot_label: string | null;
  focus_trick: string | null;
  notes: string | null;
  started_at: string;
  ended_at: string | null;
  breakthrough_note: string | null;
  clip_count: number;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface CreateSkateSessionRequest {
  spot_label?: string | null;
  focus_trick?: string | null;
  notes?: string | null;
}

export interface UpdateSkateSessionRequest {
  ended_at?: string | null;
  breakthrough_note?: string | null;
  spot_label?: string | null;
  focus_trick?: string | null;
  notes?: string | null;
}

export function isSkateSessionActive(session: SkateSession | null | undefined): boolean {
  return Boolean(session && !session.ended_at && !session.deleted_at);
}

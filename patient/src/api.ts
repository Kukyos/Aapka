// Server calls, and the shapes the engine returns.
//
// The contract is frozen in docs/09-architecture.md: every interview step comes back
// as one of three actions — ask, complete, escalate — and this file does nothing but
// carry them.

export type Lang = "en" | "hi";
export type Localised = { en: string; hi: string };

export type Option = { value: unknown; label: Localised; icon: string | null };

export type Question = {
  id: string;
  slot: string;
  section: string;
  type:
    | "single_choice"
    | "multi_choice"
    | "boolean"
    | "scale"
    | "duration"
    | "number"
    | "text";
  prompt: Localised;
  help: Localised | null;
  options: Option[];
  units: { value: string; label: Localised }[];
  min: number | null;
  max: number | null;
  anchors: { low: Localised; high: Localised } | null;
  exclusive_value: unknown;
  skippable: boolean;
  voice_preferred: boolean;
  self_report_proxy: boolean;
  provenance: string | null;
  cost_s: number;
  required: boolean;
};

export type RedFlag = {
  id: string;
  severity: "immediate" | "urgent";
  label: string;
  instruction: string;
  staff_alert: string;
};

// What the terminal remembers about a returning patient. `source` is "local" until
// ABDM credentials exist — it is rendered on screen, never quietly treated as ABHA.
export type PriorVisit = {
  source: string;
  visited_at: number;
  slots: Record<string, unknown>;
  lines: { slot: string; label: string; value: string }[];
};

export type Progress = {
  answered: number;
  asked: number;
  elapsed_s: number;
  budget_s: number;
  percent: number;
};

export type Action = {
  session_id: string;
  action: "ask" | "complete" | "escalate";
  question: Question | null;
  progress: Progress;
  red_flag: RedFlag | null;
  coverage: Record<string, unknown>;
  accepted?: boolean;
  reason?: string;
  nlu?: { method: string; confidence: number; matched: string | null } | null;
};

const BASE = "/api";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body.slice(0, 200)}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  // Where to point a patient's own phone. Null when the server cannot work out a
  // scannable address, in which case the kiosk shows no QR rather than a broken one.
  handoff: () =>
    call<{ url: string | null; source: string; secure: boolean }>("/handoff"),

  createSession: (language: Lang, mode = "ayush") =>
    call<{ session_id: string; budget_s: number }>("/session", {
      method: "POST",
      body: JSON.stringify({ language, mode }),
    }),

  consent: (id: string, body: Record<string, boolean>) =>
    call<{ accepted: boolean }>(`/session/${id}/consent`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  next: (id: string) => call<Action>(`/session/${id}/next`),

  // Brief 3.4 Step 1 — Identify. Both paths are first-class: gate G1 says a walk-in
  // carrying nothing must be able to complete an intake, so declining is an answer.
  abha: (id: string, body: { abha_id?: string | null; declined?: boolean }) =>
    call<{ ok: boolean; abha_status: string; abha_id?: string; prior_visit: PriorVisit | null }>(
      `/session/${id}/abha`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  // The returning-patient fast path. Nothing is carried until the patient has seen it
  // and said it is still true, which is why this is a separate call and not something
  // the ABHA scan does on their behalf.
  confirmPriorVisit: (id: string, confirm: boolean) =>
    call<{ ok: boolean; prefilled: string[]; returning: boolean; budget_s?: number }>(
      `/session/${id}/prior-visit`,
      { method: "POST", body: JSON.stringify({ confirm }) },
    ),

  forgetPriorVisit: (id: string) =>
    call<{ ok: boolean; forgotten: boolean }>(`/session/${id}/prior-visit`, {
      method: "DELETE",
    }),

  scanAbha: async (id: string, blob: Blob) => {
    const form = new FormData();
    form.append("file", blob, "card.jpg");
    const response = await fetch(`${BASE}/session/${id}/abha/scan`, {
      method: "POST",
      body: form,
    });
    return response.json() as Promise<{
      ok: boolean;
      found: boolean;
      abha_id?: string;
      prior_visit?: PriorVisit | null;
    }>;
  },

  summary: (id: string) =>
    call<{ sections: { key: string; title: string; lines: string[] }[] }>(
      `/session/${id}/summary`,
    ),

  answer: (
    id: string,
    body: {
      node_id: string;
      value?: unknown;
      utterance?: string;
      source: string;
      elapsed_s?: number;
    },
  ) =>
    call<Action>(`/session/${id}/answer`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  skip: (id: string, nodeId: string) =>
    call<Action>(`/session/${id}/skip`, {
      method: "POST",
      body: JSON.stringify({ node_id: nodeId }),
    }),

  // Documents and audio go as multipart, so they skip the JSON helper.
  document: async (id: string, blob: Blob) => {
    const form = new FormData();
    form.append("file", blob, "page.jpg");
    const response = await fetch(`${BASE}/session/${id}/document`, {
      method: "POST",
      body: form,
    });
    return response.json();
  },

  transcribe: async (id: string, blob: Blob, language: Lang) => {
    const form = new FormData();
    form.append("file", blob, "clip.webm");
    form.append("language", language);
    const response = await fetch(`${BASE}/session/${id}/transcribe`, {
      method: "POST",
      body: form,
    });
    return response.json() as Promise<{ text: string; ok: boolean }>;
  },

  submit: (id: string) =>
    call<{ ok: boolean; summary: unknown; privacy: { wiped: boolean } }>(
      `/session/${id}/submit`,
      { method: "POST", body: JSON.stringify({ abha_id: null }) },
    ),

  abandon: (id: string) =>
    fetch(`${BASE}/session/${id}/abandon`, { method: "POST" }).catch(() => {}),
};

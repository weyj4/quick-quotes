import type { QuoteThread } from "./types";

async function req(path: string, init?: RequestInit): Promise<QuoteThread> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const startQuote = () => req("/api/quotes", { method: "POST" });

export const getQuote = (threadId: string) => req(`/api/quotes/${threadId}`);

export const resumeQuote = (threadId: string, answers: Record<string, unknown>) =>
  req(`/api/quotes/${threadId}/resume`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });

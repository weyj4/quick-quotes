import { useCallback, useState } from "react";
import { resumeQuote, startQuote } from "./api";
import { QuoteCard, RequestPanel } from "./components/Panels";
import { SpecPanel } from "./components/SpecPanel";
import type { QuoteThread } from "./types";

export default function App() {
  const [thread, setThread] = useState<QuoteThread | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (fn: () => Promise<QuoteThread>) => {
    setBusy(true);
    setError(null);
    try {
      setThread(await fn());
      setAnswers({});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const onStart = () => run(startQuote);
  const onApply = () => {
    if (!thread) return;
    run(() => resumeQuote(thread.thread_id, answers));
  };
  const onAnswer = (path: string, value: unknown) =>
    setAnswers((a) => ({ ...a, [path]: value }));

  const reviewCount = thread?.pending
    ? Object.keys(thread.pending.gaps).length +
      Object.keys(thread.pending.confirmations).length
    : 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">Quick Quotes</span>
          <span className="brand-sub">Estimator Workbench</span>
        </div>
        <button className="btn-primary" onClick={onStart} disabled={busy}>
          {thread ? "New quote request" : "Load quote request"}
        </button>
      </header>

      {error && <div className="banner-error">{error}</div>}

      {!thread ? (
        <div className="empty">
          <p>No quote request loaded.</p>
          <p className="empty-sub">
            Load the demo request to see the agent's draft spec — every field
            tagged with where its value came from.
          </p>
        </div>
      ) : (
        <main className="workbench">
          <RequestPanel raw={thread.raw_request} />

          <div className="spec-column">
            <div className="spec-header">
              <h2>
                Quote spec{" "}
                <span className="mono spec-status" data-status={thread.spec.status}>
                  {thread.spec.status}
                </span>
              </h2>
              {thread.spec.validation_flags.length > 0 && (
                <div className="flags">
                  {thread.spec.validation_flags.map((f) => (
                    <span key={f} className="flag">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <SpecPanel
              spec={thread.spec}
              pending={thread.pending}
              answers={answers}
              onAnswer={onAnswer}
            />

            {thread.status === "needs_review" && (
              <div className="action-bar">
                <span className="action-note">
                  {reviewCount} item{reviewCount === 1 ? "" : "s"} need
                  {reviewCount === 1 ? "s" : ""} your review — pricing stays
                  locked until the spec is clean.
                </span>
                <button
                  className="btn-primary"
                  onClick={onApply}
                  disabled={busy || Object.keys(answers).length === 0}
                >
                  Apply answers & revalidate
                </button>
              </div>
            )}

            {thread.quote && <QuoteCard quote={thread.quote} />}
          </div>
        </main>
      )}
    </div>
  );
}

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

  const [draft, setDraft] = useState("");
  const onStart = () => run(() => startQuote(draft.trim() || undefined));
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
        {thread && (
          <button
            className="btn-primary"
            onClick={() => setThread(null)}
            disabled={busy}
          >
            New quote request
          </button>
        )}
      </header>

      {error && <div className="banner-error">{error}</div>}

      {!thread ? (
        <div className="intake">
          <h2>Inbound quote request</h2>
          <p className="empty-sub">
            Paste a quote request email — or run the demo request — and the
            agent drafts a spec with every field tagged with where its value
            came from.
          </p>
          <textarea
            className="intake-input"
            rows={10}
            placeholder={"From: buyer@customer.example\nSubject: quote please\n\nNeed a truckload of 12x10x8 RSCs, 32 ECT, 2-color like the last run..."}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="intake-actions">
            <button className="btn-primary" onClick={onStart} disabled={busy}>
              {draft.trim() ? "Run quote request" : "Run demo request"}
            </button>
          </div>
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
              {thread.extractor && (
                <span className="mono spec-status">
                  extractor: {thread.extractor}
                </span>
              )}
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

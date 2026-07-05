import type { Quote } from "../types";

export function RequestPanel({ raw }: { raw: string }) {
  return (
    <aside className="request-panel">
      <h3>Inbound request</h3>
      <pre className="raw-email">{raw}</pre>
      <p className="request-hint">
        Attachments and photos land here too — the agent reads them the same
        way and every extracted value points back to its source.
      </p>
    </aside>
  );
}

export function QuoteCard({ quote }: { quote: Quote }) {
  return (
    <div className="quote-card">
      <div className="quote-headline">
        <span className="quote-total">
          ${quote.extended.toLocaleString(undefined, { minimumFractionDigits: 2 })}
        </span>
        <span className="quote-sub">
          {quote.units.toLocaleString()} units @ ${quote.unit_price.toFixed(4)}
        </span>
      </div>
      <dl className="quote-meta">
        <div>
          <dt>Spec</dt>
          <dd className="mono">
            v{quote.spec_version} · {quote.spec_hash}
          </dd>
        </div>
        <div>
          <dt>Margin</dt>
          <dd className="mono">{quote.margin_source}</dd>
        </div>
        <div>
          <dt>Cost engine</dt>
          <dd className="mono">CoreERP costing API (stub)</dd>
        </div>
      </dl>
      <button className="btn-primary" disabled title="v1: routes to approver">
        Send for approval
      </button>
    </div>
  );
}

import type { PendingReview, QuoteSpec } from "../types";
import { SECTIONS, getField } from "../types";
import { ProvenanceBadge } from "./ProvenanceBadge";

export function SpecPanel({
  spec,
  pending,
  answers,
  onAnswer,
}: {
  spec: QuoteSpec;
  pending: PendingReview | null;
  answers: Record<string, unknown>;
  onAnswer: (path: string, value: unknown) => void;
}) {
  const gapPaths = new Set(Object.keys(pending?.gaps ?? {}));
  const confirmPaths = pending?.confirmations ?? {};

  return (
    <div className="spec-panel">
      {SECTIONS.map((section) => (
        <section key={section.title} className="spec-section">
          <h3>{section.title}</h3>
          <table>
            <tbody>
              {section.fields.map(([path, label]) => {
                const f = getField(spec, path);
                const isGap = gapPaths.has(path);
                const confirm = confirmPaths[path];
                const answered = path in answers;
                return (
                  <tr
                    key={path}
                    className={isGap || confirm ? "row-attention" : ""}
                  >
                    <td className="cell-label">{label}</td>
                    <td className="cell-value">
                      {isGap ? (
                        <input
                          className="gap-input"
                          placeholder={pending!.gaps[path].prompt}
                          value={(answers[path] as string) ?? ""}
                          onChange={(e) => onAnswer(path, e.target.value)}
                        />
                      ) : (
                        <span className="mono">
                          {f.value == null ? "—" : String(f.value)}
                        </span>
                      )}
                    </td>
                    <td className="cell-badge">
                      {answered && !isGap ? (
                        <span className="badge" data-prov="human_confirmed">
                          will confirm
                        </span>
                      ) : (
                        <ProvenanceBadge
                          provenance={f.provenance}
                          confidence={f.confidence}
                          source={f.source}
                          note={f.note}
                        />
                      )}
                    </td>
                    <td className="cell-action">
                      {confirm && !answered && (
                        <button
                          className="btn-confirm"
                          onClick={() => onAnswer(path, confirm.proposed)}
                          title={confirm.why ?? undefined}
                        >
                          Confirm {String(confirm.proposed)}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}

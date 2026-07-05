import type { Provenance } from "../types";

const LABEL: Record<Provenance, string> = {
  extracted: "extracted",
  resolved: "resolved",
  defaulted: "defaulted",
  inferred: "inferred",
  calculated: "calculated",
  human_confirmed: "confirmed",
};

export function ProvenanceBadge({
  provenance,
  confidence,
  source,
  note,
}: {
  provenance: Provenance | null;
  confidence: number | null;
  source: string | null;
  note: string | null;
}) {
  if (!provenance) {
    return (
      <span className="badge" data-prov="gap" title="No value — needs input">
        gap
      </span>
    );
  }
  const pct =
    confidence != null && (provenance === "extracted" || provenance === "inferred")
      ? ` ${Math.round(confidence * 100)}%`
      : "";
  const tip = [note, source && `source: ${source}`].filter(Boolean).join("\n");
  return (
    <span className="badge" data-prov={provenance} title={tip || undefined}>
      {LABEL[provenance]}
      {pct}
    </span>
  );
}

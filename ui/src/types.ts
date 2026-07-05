// Mirrors the Python QuoteSpec. The UI is a renderer of the artifact —
// it holds no domain logic; routing and validation live in the graph.

export type Provenance =
  | "extracted"
  | "resolved"
  | "defaulted"
  | "inferred"
  | "calculated"
  | "human_confirmed";

export interface SpecField<T = unknown> {
  value: T | null;
  provenance: Provenance | null;
  confidence: number | null;
  source: string | null;
  note: string | null;
}

export interface QuoteSpec {
  spec_version: number;
  status: "draft" | "validated" | "frozen";
  gaps: string[];
  needs_confirmation: string[];
  validation_flags: string[];
  // nested SpecField structure, accessed via dotted paths
  [key: string]: unknown;
}

export interface Quote {
  spec_version: number;
  spec_hash: string;
  units: number;
  unit_price: number;
  extended: number;
  margin_source: string;
}

export interface PendingReview {
  gaps: Record<string, { prompt: string }>;
  confirmations: Record<
    string,
    { proposed: unknown; why: string | null; source: string | null }
  >;
  flags: string[];
}

export interface QuoteThread {
  thread_id: string;
  raw_request: string;
  spec: QuoteSpec;
  quote: Quote | null;
  pending: PendingReview | null;
  status: "needs_review" | "priced" | "running";
}

/** Walk a dotted path ("board.flute") into the spec. */
export function getField(spec: QuoteSpec, path: string): SpecField {
  let obj: unknown = spec;
  for (const part of path.split(".")) {
    obj = (obj as Record<string, unknown>)[part];
  }
  return obj as SpecField;
}

/** Display layout: sections mirror the estimator's mental model of a spec. */
export const SECTIONS: { title: string; fields: [string, string][] }[] = [
  {
    title: "Customer",
    fields: [
      ["customer_account", "Account"],
      ["ship_to", "Ship to"],
      ["prior_spec_ref", "Prior spec"],
    ],
  },
  {
    title: "Box",
    fields: [
      ["style", "Style"],
      ["dimensions.length", "Length"],
      ["dimensions.width", "Width"],
      ["dimensions.depth", "Depth"],
      ["dimensions.units", "Units"],
      ["dimensions.convention", "Convention"],
    ],
  },
  {
    title: "Board",
    fields: [
      ["board.strength_spec", "Strength"],
      ["board.flute", "Flute"],
      ["board.board_code", "Board code"],
    ],
  },
  {
    title: "Print",
    fields: [
      ["print_spec.colors", "Colors"],
      ["print_spec.coverage", "Coverage"],
      ["print_spec.artwork_ref", "Artwork"],
    ],
  },
  {
    title: "Quantity",
    fields: [
      ["quantity.as_requested", "As requested"],
      ["quantity.units", "Units"],
      ["quantity.calc_basis", "Calc basis"],
    ],
  },
];

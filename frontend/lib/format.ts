export const ATTR: Record<string, string> = {
  yield: "Yield", expense_ratio: "Expense ratio", interest_rate: "Interest rate", apr: "APR",
  exit_load: "Exit load", min_investment: "Minimum investment", processing_fee: "Processing fee",
};
export const attrLabel = (a: string) => ATTR[a] ?? a.replace(/_/g, " ");

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null || Number.isNaN(v) ? "n/a" : `${(v * 100).toFixed(digits)}%`;

export const val = (v: number | null | undefined, unit?: string | null) => {
  if (v == null) return "n/a";
  if (unit === "INR") return v >= 1e7 ? `₹${+(v / 1e7).toFixed(2)} crore` : v >= 1e5 ? `₹${+(v / 1e5).toFixed(2)} lakh` : `₹${v.toLocaleString("en-IN")}`;
  return `${(+v).toFixed(2)}%`;
};

export const day = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";

export const shortUrl = (u?: string | null) => (u ? u.replace(/^https?:\/\/[^/]+\/demo-sites\//, "").replace(/^https?:\/\//, "") : "");

export const num = (n?: number | null) => (n == null ? "n/a" : n.toLocaleString("en-IN"));

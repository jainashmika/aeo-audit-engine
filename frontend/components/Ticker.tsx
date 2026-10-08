"use client";
import { api } from "@/lib/api";
import { attrLabel, pct, val } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";

export default function Ticker() {
  const institution = useStore((s) => s.institution);
  const theme = useStore((s) => s.theme);
  const { data } = useAsync(() => api.overview(institution), [institution]);
  if (!data) return <div className="h-8 bg-accent/80" />;
  const items: { text: string; bad: boolean }[] = [];
  for (const s of data.staleness ?? []) {
    items.push({
      text: `${s.entity} ${attrLabel(s.attribute).toLowerCase()}: the web says ${val(s.naive_answer)}, the filing says ${val(s.ground_truth)}`,
      bad: s.naive_answer !== s.ground_truth,
    });
  }
  items.push({ text: `Average extraction loss ${pct(data.sparsity.avg_extraction_loss, 0)} across ${data.sparsity.pages} pages`, bad: data.sparsity.avg_extraction_loss > 0.3 });
  for (const s of (data.severance ?? []).slice(0, 4)) {
    items.push({ text: `"${s.query}" lands with severance ${s.severance_score.toFixed(2)}`, bad: s.hydrate });
  }
  if (data.dilution) items.push({ text: `Attribute bleed into institutional products ${pct(data.dilution.attribute_bleed, 0)}`, bad: data.dilution.attribute_bleed > 0.2 });
  const run = (dup: number) => items.map((it, i) => (
    <span key={`${dup}-${i}`} className="inline-flex items-center gap-3 pr-8">
      <span aria-hidden className={it.bad ? "text-alert" : "text-truth"}>{it.bad ? "▼" : "▲"}</span>
      <span>{it.text}</span>
    </span>
  ));
  return (
    <div className={`overflow-hidden whitespace-nowrap border-b hairline ${theme === "darcula" ? "bg-paper font-mono text-[12px]" : "bg-accent/90 ui text-[13.5px]"}`}
      aria-label="Audit ticker">
      <div className="tape inline-block py-1.5 pl-4">{run(0)}{run(1)}</div>
    </div>
  );
}

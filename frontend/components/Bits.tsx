"use client";
import { ReactNode } from "react";

export function SectionHead({ title, deck, term }: { title: ReactNode; deck?: ReactNode; term: string }) {
  return (
    <header className="mb-5 border-b hairline pb-3">
      <p className="ui text-[13px] text-soft mb-1">{term}</p>
      <h2 className="headline text-[34px] leading-[1.08] font-[600] max-w-[28ch]">{title}</h2>
      {deck && <p className="italic text-soft text-[17px] mt-2 max-w-[70ch] leading-relaxed">{deck}</p>}
    </header>
  );
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <p className="ui text-soft animate-pulse py-6">{what}…</p>;
}

export function Failure({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="border border-alert/60 bg-tint/40 p-4 my-4 ui text-[14px]">
      <p className="text-alert font-semibold">The analysis service did not answer: {error}</p>
      <p className="text-soft mt-1">Check that the worker is running (docker compose ps), then try again.</p>
      {retry && <button className="btn mt-3" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Figure({ value, label, tone = "ink" }: { value: ReactNode; label: ReactNode; tone?: "ink" | "alert" | "truth" }) {
  const c = tone === "alert" ? "text-alert" : tone === "truth" ? "text-truth" : "text-ink";
  return (
    <div>
      <div className={`headline tabnum text-[40px] leading-none font-[500] ${c}`}>{value}</div>
      <div className="ui text-[13px] text-soft mt-1 max-w-[24ch]">{label}</div>
    </div>
  );
}

/** Two horizontal bars on a shared 0..1 scale (naive vs re-weighted share, static vs rendered...). */
export function Bars({ rows }: { rows: { label: string; value: number; tone: "alert" | "truth" | "soft"; note?: string }[] }) {
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="flex justify-between ui text-[13px]"><span>{r.label}</span><span className="tabnum font-mono">{r.note}</span></div>
          <div className="h-3 bg-rule/40 mt-0.5">
            <div className={`h-full ${r.tone === "alert" ? "bg-alert" : r.tone === "truth" ? "bg-truth" : "bg-soft"}`}
              style={{ width: `${Math.max(0.6, Math.min(100, r.value * 100))}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Pill({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className={`ui text-[12px] px-1.5 py-[1px] border ${ok ? "border-truth text-truth" : "border-alert text-alert"}`}>{children}</span>
  );
}

"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";

type Line = { id: number; ts: string; level: string; source: string; message: string };

export default function Wire() {
  const [lines, setLines] = useState<Line[]>([]);
  const [jobs, setJobs] = useState<any>(null);
  const [follow, setFollow] = useState(true);
  const last = useRef(0);
  const box = useRef<HTMLDivElement>(null);
  const bump = useStore((s) => s.bump);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const rows = await api.logs(last.current);
        if (rows.length && alive) {
          last.current = rows[rows.length - 1].id;
          setLines((l) => [...l, ...rows].slice(-400));
          if (rows.some((r) => /demo ready/.test(r.message)) && last.current > 0) bump();
        }
      } catch { /* the wire stays quiet while the API is unreachable */ }
      const o = await api.orchestrator();
      if (alive) setJobs(o?.jobs ?? null);
    };
    tick();
    const t = setInterval(tick, 2500);
    return () => { alive = false; clearInterval(t); };
  }, [bump]);

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines, follow]);

  const color = (l: Line) => (l.level === "ERROR" ? "text-alert" : l.level === "WARN" ? "text-kw" : "text-ink/80");
  return (
    <section aria-label="Analytics terminal" className="h-full flex flex-col bg-paper border-t hairline">
      <div className="flex items-center justify-between px-4 py-1 border-b hairline ui text-[12.5px] text-soft bg-sheet/60">
        <span><span className="text-ink font-semibold">Wire</span>, live log of retrieval metrics, severance scores and dilution alerts</span>
        <span className="flex items-center gap-4">
          {jobs && <span className="tabnum">jobs: {jobs.running} running, {jobs.succeeded} done, {jobs.failed} failed</span>}
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> follow
          </label>
        </span>
      </div>
      <div ref={box} className="flex-1 overflow-auto scroll-thin font-mono text-[12px] leading-[1.55] px-4 py-2" role="log" aria-live="polite">
        {lines.length === 0 && <p className="text-soft">Waiting for the first log line from the worker.</p>}
        {lines.map((l) => (
          <div key={l.id} className="whitespace-pre-wrap">
            <span className="text-soft">{new Date(l.ts).toLocaleTimeString("en-GB")}</span>{" "}
            <span className="text-fn">{l.source.padEnd(9)}</span>{" "}
            <span className={color(l)}>{l.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

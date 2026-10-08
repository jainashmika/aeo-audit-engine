"use client";
import { ReactNode, useState } from "react";
import { api } from "@/lib/api";
import { attrLabel, pct, shortUrl } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { useStore } from "@/lib/store";

function Group({ title, count, children, open = true }: { title: string; count?: number; children: ReactNode; open?: boolean }) {
  const [o, setO] = useState(open);
  return (
    <section className="mb-3">
      <button onClick={() => setO(!o)} aria-expanded={o}
        className="w-full flex items-baseline justify-between ui text-[13px] font-semibold border-b hairline pb-1 mb-1 text-left">
        <span><span aria-hidden className="inline-block w-3 text-soft">{o ? "▾" : "▸"}</span>{title}</span>
        {count != null && <span className="text-soft font-normal tabnum">{count}</span>}
      </button>
      {o && <div>{children}</div>}
    </section>
  );
}

export default function IndexPane() {
  const { institution, focus, setFocus, openHub, openScrape, hubPath, section, scrapeUrl } = useStore();
  const ents = useAsync(() => api.entities(institution), [institution]);
  const scrapes = useAsync(() => api.scrapes(institution), [institution]);
  const files = useAsync(() => api.manifest(institution), [institution]);

  const ns = (n: string) => (ents.data ?? []).filter((e) => e.namespace_type === n && e.attributes.length);
  const item = "block w-full text-left px-2 py-[3px] text-[13.5px] leading-snug hover:bg-tint/70 rounded-[var(--radius)]";

  return (
    <nav aria-label="Index" className="h-full overflow-auto scroll-thin bg-sheet px-3 py-3">
      <p className="headline text-lg mb-2">Index</p>
      {ents.error && <p className="text-alert text-sm">{ents.error}</p>}
      {["Institutional", "Retail"].map((n) => (
        <Group key={n} title={`${n} products`} count={ns(n).length}>
          {ns(n).map((e) => (
            <div key={e.id} className="mb-1">
              <div className="px-2 text-[13.5px] font-medium">{e.entity_name}</div>
              <div className="flex flex-wrap gap-x-2 px-2">
                {e.attributes.map((a: string) => {
                  const on = focus?.entityId === e.id && focus?.attribute === a && section === "stale";
                  return (
                    <button key={a} onClick={() => setFocus({ entityId: e.id, entityName: e.entity_name, attribute: a })}
                      className={`ui text-[12.5px] underline-offset-2 hover:underline ${on ? "text-alert underline" : "text-soft"}`}>
                      {attrLabel(a).toLowerCase()}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </Group>
      ))}
      <Group title="Pages crawled" count={scrapes.data?.length}>
        {(scrapes.data ?? []).map((s) => (
          <button key={s.id} onClick={() => openScrape(s.url)}
            className={`${item} flex justify-between gap-2 ${scrapeUrl === s.url && section === "hidden" ? "bg-tint" : ""}`}>
            <span className="truncate font-mono text-[12px]">{shortUrl(s.url)}</span>
            <span className={`tabnum font-mono text-[12px] ${s.extraction_loss > 0.5 ? "text-alert" : "text-soft"}`}>{pct(s.extraction_loss, 0)}</span>
          </button>
        ))}
      </Group>
      <Group title="Machine hub files" count={files.data?.length} open={false}>
        {(files.data ?? []).map((f) => (
          <button key={f.path} onClick={() => openHub(f.path)}
            className={`${item} font-mono text-[12px] truncate ${hubPath === f.path && section === "hub" ? "bg-tint" : ""}`}>
            {f.path.replace("institutional-data/", "")}
          </button>
        ))}
      </Group>
    </nav>
  );
}

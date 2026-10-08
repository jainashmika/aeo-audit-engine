"use client";
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { api } from "@/lib/api";
import { num, pct, val } from "@/lib/format";
import { useAsync, usePalette } from "@/lib/hooks";
import { useStore } from "@/lib/store";
import Markdown from "../Markdown";
import { Failure, Figure, Loading, SectionHead } from "../Bits";

export default function BrandBleed() {
  const { institution, openHub } = useStore();
  const p = useAsync(() => api.partition(institution), [institution]);
  const ents = useAsync(() => api.entities(institution), [institution]);
  const matrix = useAsync(() => api.hubFile(institution, "institutional-data/matrix.md"), [institution]);
  const target = (ents.data ?? []).find((e) => e.namespace_type === "Institutional" && e.entity_kind === "product" && e.attributes.includes("expense_ratio"));
  const ans = useAsync(() => (target ? api.namespaced(institution, target.slug, "expense_ratio") : Promise.resolve(null)), [institution, target?.slug]);
  const pal = usePalette();
  if (p.error) return <Failure error={p.error} retry={p.reload} />;
  if (!p.data) return <Loading what="Partitioning the brand's text into namespaces" />;
  const d = p.data;
  const pts = (ns: string) => (d.scatter ?? []).filter((s: any) => s.namespace === ns);
  const bleed = d.attribute_bleed;

  return (
    <article className="max-w-[1180px]">
      <SectionHead term="Sub-entity partitioning, semantic dilution"
        title={bleed.rate > 0.2 ? `${pct(bleed.rate, 0)} of outside claims about the institutional products carry retail figures` : "Institutional products keep their own figures in the public record"}
        deck="Years of mass-market text pull the brand's overall vector toward retail. The engine splits every text node into a Retail or Institutional namespace, measures how much each side leaks into the other, and publishes a matrix that tells answer engines to keep them apart." />
      <div className="grid sm:grid-cols-3 gap-6 mb-6">
        <Figure value={d.semantic_dilution_index.toFixed(2)} label="dilution index (0.5 is balanced, higher leans retail)" tone={d.semantic_dilution_index > 0.5 ? "alert" : "truth"} />
        <Figure value={pct(bleed.rate, 0)} label={`attribute bleed across ${num(bleed.third_party_claims)} third-party claims`} tone={bleed.rate > 0.2 ? "alert" : "truth"} />
        <Figure value={d.centroid_separation.toFixed(2)} label="cosine distance between the two namespace centroids" />
      </div>
      <div className="grid lg:grid-cols-[1fr_380px] gap-8">
        <section>
          <h3 className="ui text-[14px] font-semibold mb-1">Every unique text node, placed by its similarity to each namespace</h3>
          <div className="h-[320px] border hairline bg-paper/50">
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 12, right: 16, bottom: 24, left: 0 }}>
                <CartesianGrid stroke={pal.rule} strokeDasharray="2 4" />
                <XAxis type="number" dataKey="x" name="Retail similarity" tick={{ fontSize: 11, fill: pal.soft }} stroke={pal.rule}
                  label={{ value: "similarity to retail centroid", position: "insideBottom", offset: -12, fontSize: 11, fill: pal.soft }} />
                <YAxis type="number" dataKey="y" name="Institutional similarity" tick={{ fontSize: 11, fill: pal.soft }} stroke={pal.rule} width={44} />
                <ZAxis type="number" dataKey="weight" range={[30, 420]} />
                <Tooltip cursor={false} content={({ payload }) => payload?.[0] ? (
                  <div className="bg-paper border border-ink p-2 text-[12px] max-w-[280px]">{(payload[0].payload as any).label}<br /><span className="text-soft">{(payload[0].payload as any).source}, weight {(payload[0].payload as any).weight}</span></div>) : null} />
                <Legend verticalAlign="top" height={24} wrapperStyle={{ fontSize: 12 }} />
                <Scatter name="Retail" data={pts("Retail")} fill={pal.accent} stroke={pal.alert} fillOpacity={0.7} isAnimationActive={false} />
                <Scatter name="Institutional" data={pts("Institutional")} fill={pal.truth} fillOpacity={0.7} isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          {bleed.examples.length > 0 && <>
            <h3 className="ui text-[14px] font-semibold mt-6 mb-1">Retail figures attached to institutional products</h3>
            <table className="ledger w-full text-[13.5px] tabnum"><thead><tr><th>Claim in the wild</th><th>Occurrences</th></tr></thead>
              <tbody>{bleed.examples.map((e: any) => <tr key={e.claim}><td>{e.claim}</td><td className="font-mono">{num(e.count)}</td></tr>)}</tbody></table>
          </>}
        </section>
        <aside>
          {ans.data && (
            <div className="border hairline p-4 bg-sheet/50 mb-6">
              <p className="ui text-[13px] text-soft">Asked: expense ratio of the {ans.data.entity}</p>
              <dl className="mt-2 grid grid-cols-[1fr_auto] gap-y-2 items-baseline">
                <dt className="text-[15px]">Retrieval over the whole brand</dt>
                <dd className={`headline text-3xl tabnum ${ans.data.hallucination_prevented ? "text-alert" : ""}`}>{val(ans.data.brand_level_answer)}</dd>
                <dt className="text-[15px]">Retrieval inside the Institutional namespace</dt>
                <dd className="headline text-3xl tabnum text-truth">{val(ans.data.partitioned_answer)}</dd>
              </dl>
            </div>
          )}
          <div className="border-t-2 border-ink pt-2">
            {matrix.data ? <Markdown src={matrix.data} /> : <Loading what="Composing the matrix" />}
            <button className="btn mt-2" onClick={() => openHub("institutional-data/matrix.md")}>Open matrix.md in the hub</button>
          </div>
        </aside>
      </div>
    </article>
  );
}

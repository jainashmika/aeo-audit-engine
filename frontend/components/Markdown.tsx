"use client";
/* Minimal renderer for the Machine Hub's Markdown (headings, tables, lists, quotes, links, bold). */
import { ReactNode } from "react";

function inline(s: string, key: number): ReactNode {
  const parts: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)|_([^_]+)_/g;
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(s))) {
    parts.push(s.slice(last, m.index));
    if (m[1]) parts.push(<strong key={i++}>{m[1]}</strong>);
    else if (m[2]) parts.push(<code key={i++} className="font-mono text-[0.85em] bg-tint/60 px-1">{m[2]}</code>);
    else if (m[3]) parts.push(<a key={i++} className="underline decoration-alert/60 underline-offset-2" href={m[4]} target="_blank" rel="noreferrer">{m[3]}</a>);
    else parts.push(<em key={i++}>{m[5]}</em>);
    last = re.lastIndex;
  }
  parts.push(s.slice(last));
  return <span key={key}>{parts}</span>;
}

export default function Markdown({ src }: { src: string }) {
  const lines = src.split("\n");
  const out: ReactNode[] = [];
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[\s|:-]+\|$/.test(lines[i])) rows.push(lines[i].slice(1, -1).split("|").map((c) => c.trim()));
        i++;
      }
      const [head, ...body] = rows;
      out.push(
        <table key={k++} className="ledger w-full my-4 text-[14px] tabnum">
          <thead><tr>{head.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
          <tbody>{body.map((r, a) => <tr key={a}>{r.map((c, b) => <td key={b} className={b === 0 ? "ui text-soft" : ""}>{inline(c, b)}</td>)}</tr>)}</tbody>
        </table>);
      continue;
    }
    if (/^# /.test(l)) out.push(<h2 key={k++} className="headline text-3xl mt-2 mb-3">{l.slice(2)}</h2>);
    else if (/^## /.test(l)) out.push(<h3 key={k++} className="headline text-xl mt-6 mb-2 border-b hairline pb-1">{l.slice(3)}</h3>);
    else if (/^### /.test(l)) out.push(<h4 key={k++} className="headline text-lg mt-4 mb-1">{l.slice(4)}</h4>);
    else if (/^> /.test(l)) out.push(<p key={k++} className="italic text-soft border-l-2 border-accent pl-3 my-3">{inline(l.slice(2), 0)}</p>);
    else if (/^(- |\d+\. )/.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^(- |\d+\. )/.test(lines[i])) items.push(lines[i++].replace(/^(- |\d+\. )/, ""));
      out.push(<ul key={k++} className="list-disc pl-6 my-2 space-y-1">{items.map((t, j) => <li key={j}>{inline(t, j)}</li>)}</ul>);
      continue;
    } else if (l.trim()) out.push(<p key={k++} className="my-2 leading-relaxed">{inline(l, 0)}</p>);
    i++;
  }
  return <div className="text-[15px]">{out}</div>;
}

"use client";
import { Fragment, ReactNode } from "react";

const esc = (s: string) => s;

function json(src: string): ReactNode[] {
  const re = /("(?:\\.|[^"\\])*")(\s*:)?|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|\b(true|false|null)\b/g;
  const out: ReactNode[] = [];
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(src))) {
    out.push(esc(src.slice(last, m.index)));
    if (m[1]) out.push(<span key={i++} className={m[2] ? "f" : "s"}>{m[1]}</span>, m[2] ?? "");
    else if (m[3]) out.push(<span key={i++} className="n">{m[3]}</span>);
    else out.push(<span key={i++} className="k">{m[4]}</span>);
    last = re.lastIndex;
  }
  out.push(src.slice(last));
  return out;
}

function js(src: string): ReactNode[] {
  const re = /(\/\*[\s\S]*?\*\/|\/\/.*$)|('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")|\b(var|function|return|if|new|document|typeof)\b|(\b\d+(?:\.\d+)?\b)|(\.\w+(?=\())/gm;
  const out: ReactNode[] = [];
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(src))) {
    out.push(src.slice(last, m.index));
    const cls = m[1] ? "c" : m[2] ? "s" : m[3] ? "k" : m[4] ? "n" : "f";
    out.push(<span key={i++} className={cls}>{m[0]}</span>);
    last = re.lastIndex;
  }
  out.push(src.slice(last));
  return out;
}

function md(src: string): ReactNode[] {
  return src.split("\n").map((line, i) => {
    let cls = "";
    if (/^#/.test(line)) cls = "k";
    else if (/^\|/.test(line)) cls = "n";
    else if (/^>/.test(line)) cls = "c";
    else if (/^- /.test(line)) cls = "s";
    return <Fragment key={i}>{cls ? <span className={cls}>{line}</span> : line}{"\n"}</Fragment>;
  });
}

export default function CodeView({ code, lang, className = "" }: { code: string; lang: "json" | "js" | "md" | "text"; className?: string }) {
  const body = lang === "json" ? json(code) : lang === "js" ? js(code) : lang === "md" ? md(code) : code;
  const lines = code.split("\n").length;
  return (
    <div className={`code flex overflow-auto scroll-thin bg-paper/60 border hairline ${className}`}>
      <pre aria-hidden className="select-none text-right pr-3 pl-3 py-3 text-soft/70 border-r hairline">
        {Array.from({ length: lines }, (_, i) => i + 1).join("\n")}
      </pre>
      <pre className="px-4 py-3 whitespace-pre min-w-0">{body}</pre>
    </div>
  );
}

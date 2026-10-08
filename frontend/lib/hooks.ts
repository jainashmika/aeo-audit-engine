"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useStore } from "./store";

/** Fetch with loading/error state; re-runs when deps or the global refresh key change. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const refreshKey = useStore((s) => s.refreshKey);
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null, error: null, loading: true,
  });
  const live = useRef(true);
  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn().then(
      (data) => live.current && setState({ data, error: null, loading: false }),
      (e) => live.current && setState({ data: null, error: String(e?.message ?? e), loading: false }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refreshKey]);
  useEffect(() => {
    live.current = true;
    run();
    return () => { live.current = false; };
  }, [run]);
  return { ...state, reload: run };
}

/** Chart colours resolved from the active theme's CSS variables. */
export function usePalette() {
  const theme = useStore((s) => s.theme);
  const [p, setP] = useState<Record<string, string>>({});
  useEffect(() => {
    const cs = getComputedStyle(document.documentElement);
    const get = (n: string) => `rgb(${cs.getPropertyValue(`--${n}`).trim().split(/\s+/).join(",")})`;
    setP(Object.fromEntries(["paper", "sheet", "ink", "soft", "rule", "accent", "tint", "alert", "truth", "kw", "str", "num", "fn"]
      .map((n) => [n, get(n)])));
  }, [theme]);
  return p;
}

"use client";
import dynamic from "next/dynamic";

// The dashboard is a live, client-only workstation (theme from localStorage, dates in the viewer's
// locale, polling terminal), so it is rendered in the browser to avoid hydration mismatches.
const Shell = dynamic(() => import("@/components/Shell"), { ssr: false });

export default function Page() {
  return <Shell />;
}

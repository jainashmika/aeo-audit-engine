import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Answer-Engine Ledger",
  description: "AEO Audit Engine: quantifying LLM hallucination and factual drift in financial services.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: "try{if(localStorage.getItem('aeo-theme')==='darcula')document.documentElement.dataset.theme='darcula'}catch(e){}" }} />
      </head>
      <body>{children}</body>
    </html>
  );
}

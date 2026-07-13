import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Neural Intelligence Network",
  description: "Cross-domain synthesis dashboard for the Neural Orchestrator middleware.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090b12] text-slate-200 antialiased">{children}</body>
    </html>
  );
}

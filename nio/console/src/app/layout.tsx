import type { Metadata } from "next";
import type { ReactNode } from "react";
import CodyPet from "@/components/cody/CodyPet";
import "./globals.css";

export const metadata: Metadata = {
  title: "NIO — Neural Intelligence Orchestrator",
  description: "Orchestrator console wired to NIO middleware and twin/model-manifest.json tier routing.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de" className="dark">
      <body className="min-h-screen bg-[#090b12] text-slate-200 antialiased">
        {children}
        <CodyPet />
      </body>
    </html>
  );
}

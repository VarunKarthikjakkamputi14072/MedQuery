import type { Metadata } from "next";
import "./globals.css";
import { TopNav } from "@/components/TopNav";

export const metadata: Metadata = {
  title: "MedQuery — Clinical Document Intelligence",
  description:
    "Upload, embed, and query clinical documents with grounded citations and risk flagging.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-clinical-bg text-slate-100">
        <div className="clinical-grid min-h-screen">
          <TopNav />
          <main className="mx-auto w-full max-w-7xl px-6 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

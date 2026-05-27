"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/query", label: "Query" },
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="border-b border-clinical-border bg-clinical-bg/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md border border-clinical-border bg-clinical-surface text-clinical-accent">
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
              <path
                d="M12 3v18M3 12h18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div>
            <p className="font-mono text-sm uppercase tracking-[0.18em] text-clinical-accent">
              MedQuery
            </p>
            <p className="text-xs text-clinical-subtle">
              Clinical Document Intelligence
            </p>
          </div>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={clsx(
                  "rounded-md px-3 py-2 text-sm font-medium transition",
                  active
                    ? "bg-clinical-surface text-clinical-accent shadow-glow"
                    : "text-slate-300 hover:bg-clinical-surface/60 hover:text-clinical-accent",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

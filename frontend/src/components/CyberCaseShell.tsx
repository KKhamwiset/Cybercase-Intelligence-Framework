"use client";

import Link from "next/link";
import type { ReactNode } from "react";

type ActiveNav = "Home" | "Investigate" | "Reports";

const NAV_ITEMS: { label: ActiveNav; href: string }[] = [
  { label: "Home", href: "/" },
  { label: "Investigate", href: "/cases" },
  { label: "Reports", href: "/reports" },
];

type CyberCaseShellProps = {
  activeNav: ActiveNav;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
};

export default function CyberCaseShell({
  activeNav,
  eyebrow = "CyberCase Intelligence Framework",
  title,
  subtitle,
  children,
  actions,
}: CyberCaseShellProps) {
  return (
    <main className="h-screen overflow-hidden bg-white text-black">
      <div className="flex h-full w-full overflow-hidden bg-white">
        <aside className="hidden w-56 shrink-0 flex-col border-r border-black/10 bg-white px-4 py-5 md:flex">
          <Link
            href="/"
            className="flex items-center gap-2 text-base font-black tracking-tight"
          >
            <span className="flex h-7 w-7 items-center justify-center bg-black text-[10px] text-white">
              CC
            </span>
            <span>CyberCase</span>
          </Link>

          <p className="mt-2 text-[10px] font-bold uppercase tracking-widest text-neutral">
            Intelligence Framework
          </p>

          <nav className="mt-7 space-y-1 text-[11px] font-bold">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className={`block px-3 py-2 transition ${
                  item.label === activeNav
                    ? "bg-black text-white"
                    : "text-neutral hover:bg-neutral-100 hover:text-black"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="mt-auto border-t border-black/10 pt-4">
            <p className="text-xs font-semibold text-neutral">Workspace</p>
            <p className="mt-1 truncate text-sm font-black">
              CyberCase Operations
            </p>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-white px-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center bg-black text-[10px] font-black text-white md:hidden">
                CC
              </span>

              <div className="min-w-0">
                <p className="truncate text-[10px] font-black uppercase tracking-widest text-neutral">
                  {eyebrow}
                </p>
                <p className="truncate text-sm font-black">{title}</p>

                {subtitle ? (
                  <p className="hidden truncate text-[11px] font-semibold text-neutral sm:block">
                    {subtitle}
                  </p>
                ) : null}
              </div>
            </div>

            {actions ? (
              <div className="flex shrink-0 items-center gap-2">{actions}</div>
            ) : null}
          </header>

          <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
        </section>
      </div>
    </main>
  );
}

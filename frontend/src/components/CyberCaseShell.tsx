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

function Navigation({ activeNav, mobile = false }: { activeNav: ActiveNav; mobile?: boolean }) {
  return (
    <nav
      aria-label={mobile ? "Mobile navigation" : "Primary navigation"}
      className={
        mobile
          ? "flex min-w-max items-center gap-1 px-3"
          : "mt-8 space-y-1.5 text-xs font-bold"
      }
    >
      {NAV_ITEMS.map((item) => {
        const isActive = item.label === activeNav;
        return (
          <Link
            key={item.label}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={
              mobile
                ? `relative px-3 py-3 text-[11px] font-extrabold transition-colors duration-150 focus-visible:outline-offset-[-2px] motion-reduce:transition-none ${
                    isActive
                      ? "text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-accent"
                      : "text-muted hover:text-ink"
                  }`
                : `relative block border border-transparent px-3 py-2.5 transition-colors duration-150 motion-reduce:transition-none ${
                    isActive
                      ? "border-white/10 bg-white/10 pl-5 text-white before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:bg-accent-strong"
                      : "text-white/60 hover:border-white/10 hover:bg-white/5 hover:text-white"
                  }`
            }
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default function CyberCaseShell({
  activeNav,
  eyebrow = "CyberCase Intelligence Framework",
  title,
  subtitle,
  children,
  actions,
}: CyberCaseShellProps) {
  return (
    <div className="h-screen overflow-hidden bg-canvas text-ink">
      <div className="flex h-full w-full overflow-hidden">
        <aside className="hidden w-60 shrink-0 flex-col border-r border-white/10 bg-ink px-5 py-6 text-white md:flex">
          <Link
            href="/"
            className="group flex items-center gap-3 text-base font-black tracking-tight focus-visible:outline-offset-4"
          >
            <span className="flex h-8 w-8 items-center justify-center border border-white/15 bg-white text-[10px] font-black text-ink transition-colors duration-150 group-hover:border-accent-strong group-hover:bg-accent-strong group-hover:text-white motion-reduce:transition-none">
              CC
            </span>
            <span>CyberCase</span>
          </Link>

          <p className="mt-3 text-[9px] font-bold uppercase tracking-[0.2em] text-white/45">
            Intelligence Framework
          </p>

          <Navigation activeNav={activeNav} />

          <div className="mt-auto border-t border-white/10 pt-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-white/40">
              Workspace
            </p>
            <p className="mt-1.5 truncate text-sm font-black text-white/90">
              CyberCase Operations
            </p>
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col bg-canvas">
          <header className="flex min-h-16 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-ink/10 bg-surface px-4 py-3 sm:flex-nowrap md:px-7">
            <div className="flex min-w-0 items-center gap-3">
              <Link
                href="/"
                aria-label="CyberCase home"
                className="flex h-9 w-9 shrink-0 items-center justify-center bg-ink text-[10px] font-black text-white md:hidden"
              >
                CC
              </Link>

              <div className="min-w-0">
                <p className="truncate text-[9px] font-black uppercase tracking-[0.17em] text-muted">
                  {eyebrow}
                </p>
                <p className="mt-0.5 truncate text-sm font-black text-ink">{title}</p>

                {subtitle ? (
                  <p className="hidden truncate text-[11px] font-semibold text-muted sm:block">
                    {subtitle}
                  </p>
                ) : null}
              </div>
            </div>

            {actions ? (
              <div className="flex w-full shrink-0 items-center justify-end gap-2 sm:w-auto">
                {actions}
              </div>
            ) : null}
          </header>

          <div className="shrink-0 overflow-x-auto border-b border-ink/10 bg-surface md:hidden">
            <Navigation activeNav={activeNav} mobile />
          </div>

          <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
        </section>
      </div>
    </div>
  );
}
